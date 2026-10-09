import json
import logging
import sqlite3
import time
import uuid
from collections.abc import AsyncIterator

import fastapi
import pydantic
from sse_starlette import sse

from lightdash_companion_integration_spike import config
from lightdash_companion_integration_spike.agent import agent as agent_module
from lightdash_companion_integration_spike.agent import history
from lightdash_companion_integration_spike.domain import blocks
from lightdash_companion_integration_spike.lightdash import content, embed, mcp_client, queries
from lightdash_companion_integration_spike.storage import sqlite

logger = logging.getLogger(__name__)

router = fastapi.APIRouter(prefix="/api")

TITLE_LENGTH = 60


class NewMessage(pydantic.BaseModel):
    text: str
    user_attributes: dict[str, str] | None = None


class Feedback(pydantic.BaseModel):
    rating: str


class RerunRequest(pydantic.BaseModel):
    title: str
    description: str = ""
    query_config: dict[str, object]
    user_attributes: dict[str, str] | None = None


def _settings(request: fastapi.Request) -> config.Settings:
    return request.app.state.settings


def _connection(request: fastapi.Request) -> sqlite3.Connection:
    return request.app.state.connection


@router.post("/threads")
def create_thread(request: fastapi.Request) -> dict[str, str]:
    thread_id = sqlite.create_thread(
        connection=_connection(request), title=sqlite.DEFAULT_THREAD_TITLE
    )
    return {"id": thread_id}


@router.get("/threads")
def list_threads(request: fastapi.Request) -> list[dict[str, str]]:
    return sqlite.list_threads(connection=_connection(request))


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str, request: fastapi.Request) -> list[dict[str, object]]:
    messages = sqlite.list_messages(connection=_connection(request), thread_id=thread_id)
    return [
        {
            "id": message.id,
            "role": message.role,
            "text": message.text,
            "blocks": blocks.BlockList.dump_python(message.blocks),
            "feedback": sqlite.get_feedback(connection=_connection(request), message_id=message.id),
        }
        for message in messages
    ]


@router.post("/threads/{thread_id}/messages")
async def post_message(
    thread_id: str, body: NewMessage, request: fastapi.Request
) -> sse.EventSourceResponse:
    return sse.EventSourceResponse(
        _stream_answer(
            thread_id=thread_id,
            body=body,
            settings=_settings(request),
            connection=_connection(request),
        )
    )


async def _stream_answer(
    *, thread_id: str, body: NewMessage, settings: config.Settings, connection: sqlite3.Connection
) -> AsyncIterator[dict[str, str]]:
    steps: list[str] = []
    started = time.monotonic()
    logger.info("turn start thread=%s question=%r", thread_id, body.text)

    async def on_step(step: str) -> None:
        steps.append(step)

    try:
        async for event in _run_turn(
            thread_id=thread_id, body=body, settings=settings, connection=connection,
            steps=steps, started=started,
        ):
            yield event
    except Exception as error:
        # Reported to the browser so a failed turn is visible, then re-raised for the server log.
        logger.exception("turn failed thread=%s", thread_id)
        yield {"event": "error", "data": json.dumps({"message": f"{type(error).__name__}: {error}"})}


async def _run_turn(
    *,
    thread_id: str,
    body: NewMessage,
    settings: config.Settings,
    connection: sqlite3.Connection,
    steps: list[str],
    started: float,
) -> AsyncIterator[dict[str, str]]:
    stored = sqlite.list_messages(connection=connection, thread_id=thread_id)
    existing = sqlite.list_artifact_versions(connection=connection, thread_id=thread_id)
    client = mcp_client.create_client(
        settings=settings, token=_token_for(settings=settings, user_attributes=body.user_attributes),
        attributes=body.user_attributes,
    )
    async def on_step(step: str) -> None:
        steps.append(step)

    async with client:
        deps = agent_module.AgentDeps(
            settings=settings, client=client, connection=connection, thread_id=thread_id, on_step=on_step
        )
        agent = agent_module.build_agent()
        async with agent.iter(
            body.text,
            deps=deps,
            message_history=history.build_message_history(stored=stored, existing_artifacts=existing),
        ) as run:
            async for _node in run:
                while steps:
                    yield {"event": "tool_step", "data": json.dumps({"step": steps.pop(0)})}
            answer = run.result.output if run.result else None

    logger.info(
        "turn done thread=%s charts=%d seconds=%.1f",
        thread_id, len(deps.chart_blocks), time.monotonic() - started,
    )
    if answer is None:
        yield {"event": "error", "data": json.dumps({"message": "The agent produced no answer."})}
        return

    answer_blocks: list[blocks.Block] = [
        blocks.MarkdownBlock(text=answer.text),
        *deps.chart_blocks,
        blocks.FollowUpsBlock(suggestions=answer.follow_ups),
    ]
    sqlite.add_message(
        connection=connection, thread_id=thread_id, role=sqlite.USER_ROLE, text=body.text,
        message_blocks=[blocks.MarkdownBlock(text=body.text)],
    )
    sqlite.title_thread_if_untitled(connection=connection, thread_id=thread_id, question=body.text)
    message_id = sqlite.add_message(
        connection=connection, thread_id=thread_id, role=sqlite.ASSISTANT_ROLE, text=answer.text,
        message_blocks=answer_blocks,
    )
    for chart in deps.chart_blocks:
        sqlite.save_artifact_version(
            connection=connection, thread_id=thread_id, artifact_id=chart.artifact_id,
            title=chart.title, query_args=chart.query_args, message_id=message_id,
        )
    yield {
        "event": "answer",
        "data": json.dumps({"id": message_id, "blocks": blocks.BlockList.dump_python(answer_blocks)}),
    }


def _token_for(*, settings: config.Settings, user_attributes: dict[str, str] | None) -> str:
    if user_attributes and settings.lightdash_admin_token:
        return settings.lightdash_admin_token
    return settings.lightdash_token


@router.post("/messages/{message_id}/feedback")
def post_feedback(message_id: str, body: Feedback, request: fastapi.Request) -> dict[str, str]:
    sqlite.save_feedback(connection=_connection(request), message_id=message_id, rating=body.rating)
    return {"status": "saved"}


@router.post("/queries/rerun")
async def rerun_query(body: RerunRequest, request: fastapi.Request) -> dict[str, object]:
    settings = _settings(request)
    client = mcp_client.create_client(
        settings=settings,
        token=_token_for(settings=settings, user_attributes=body.user_attributes),
        attributes=body.user_attributes,
    )
    async with client:
        try:
            result = await queries.run_metric_query(
                client=client,
                project_uuid=settings.project_uuid,
                agent_uuid=settings.agent_uuid,
                arguments={
                    "title": body.title,
                    "description": body.description,
                    "queryConfig": body.query_config,
                    "chartConfig": None,
                },
            )
        except queries.MissingStructuredResult as error:
            raise fastapi.HTTPException(status_code=422, detail=error.server_message) from error
    return {
        "queryUuid": result.query_uuid,
        "rows": list(result.rows),
        "fields": dict(result.fields),
        "exploreUrl": result.explore_url,
    }


class ExploreRequest(pydantic.BaseModel):
    query_config: dict[str, object]
    user_attributes: dict[str, str] = pydantic.Field(default_factory=dict)


class EmbedSecretMissing(Exception):
    pass


@router.post("/explore-url")
def explore_url(body: ExploreRequest, request: fastapi.Request) -> dict[str, str]:
    settings = _settings(request)
    if settings.embed_secret is None:
        raise fastapi.HTTPException(status_code=501, detail="EMBED_SECRET is not configured")
    explore_name = str(body.query_config.get("exploreName", ""))
    column_order = [
        *map(str, body.query_config.get("dimensions", [])),  # type: ignore[arg-type]  # validated by the explore state builder
        *map(str, body.query_config.get("metrics", [])),  # type: ignore[arg-type]  # validated by the explore state builder
    ]
    token = embed.mint_token(
        secret=settings.embed_secret,
        payload=embed.build_jwt_payload(
            project_uuid=settings.project_uuid,
            user_attributes=body.user_attributes,
            now=embed.now_seconds(),
        ),
    )
    return {
        "url": embed.build_explore_url(
            site_url=settings.lightdash_url,
            project_uuid=settings.project_uuid,
            explore_name=explore_name,
            saved_chart_version=embed.explore_state(
                explore_name=explore_name,
                query_config=body.query_config,
                column_order=column_order,
            ),
            token=token,
        )
    }


class SaveChartRequest(pydantic.BaseModel):
    title: str
    description: str = ""
    query_config: dict[str, object]


@router.post("/charts/save")
async def save_chart(body: SaveChartRequest, request: fastapi.Request) -> dict[str, str | None]:
    settings = _settings(request)
    if settings.sandbox_space_slug is None:
        raise fastapi.HTTPException(status_code=501, detail="SANDBOX_SPACE_SLUG is not configured")
    try:
        chart_content = content.build_bar_chart_content(
            title=body.title,
            description=body.description,
            slug=content.slugify(title=body.title, unique_suffix=uuid.uuid4().hex),
            space_slug=settings.sandbox_space_slug,
            query_config=body.query_config,
        )
    except content.UnsupportedChartShape as error:
        raise fastapi.HTTPException(
            status_code=422, detail="Only single-dimension charts can be saved in this spike"
        ) from error
    client = mcp_client.create_client(settings=settings, token=settings.lightdash_token)
    async with client:
        try:
            saved = await content.create_chart(
                client=client,
                project_uuid=settings.project_uuid,
                agent_uuid=settings.agent_uuid,
                content=chart_content,
            )
        except content.SaveRejected as error:
            raise fastapi.HTTPException(status_code=422, detail=error.server_message) from error
    return {"href": f"{settings.lightdash_url.rstrip('/')}{saved.href}", "uuid": saved.uuid}
