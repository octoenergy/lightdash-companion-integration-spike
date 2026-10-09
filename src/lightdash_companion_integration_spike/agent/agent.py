import logging
import sqlite3
import uuid
from collections.abc import Awaitable, Callable, Mapping

import attrs
import pydantic
import pydantic_ai
from fastmcp import Client

from lightdash_companion_integration_spike import config
from lightdash_companion_integration_spike.agent import chart_config as chart_config_module
from lightdash_companion_integration_spike.agent import summary
from lightdash_companion_integration_spike.domain import artifacts, blocks, query_spec
from lightdash_companion_integration_spike.lightdash import mcp_client, queries

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
You answer data questions using the Lightdash semantic layer.
1. Call find_fields to discover explores and field ids. Only use ids it returns.
2. Call run_query to get data. Pick the explore whose name matches the question.
   Use the metrics that find_fields lists (kind "metric"). Never write SQL or table
   calculations: if no metric fits, say so instead of inventing one.
3. To change an earlier chart (add a filter, split by month, change metric), reuse its
   artifact_id so it becomes a new version. For a different question use artifact_id "new".
4. The user sees the chart and table automatically. Reply with a short explanation and
   2-3 follow-ups. Never list every row.
5. Write each follow-up as a request the user can click to run, phrased as an instruction
   such as "Split by month" or "Show only the last 30 days". Never phrase a follow-up as a
   question to the user ("Do you want...?").
"""

OPENAI_MODEL = "openai:gpt-5.4"


class AgentAnswer(pydantic.BaseModel):
    text: str
    follow_ups: list[str] = pydantic.Field(default_factory=list)


@attrs.mutable
class AgentDeps:
    settings: config.Settings
    client: Client
    connection: sqlite3.Connection
    thread_id: str
    chart_blocks: list[blocks.ChartBlock] = attrs.Factory(list)
    on_step: Callable[[str], Awaitable[None]] | None = None


async def _announce(*, deps: AgentDeps, step: str) -> None:
    if deps.on_step is not None:
        await deps.on_step(step)


def build_agent(*, model: str = OPENAI_MODEL) -> pydantic_ai.Agent[AgentDeps, AgentAnswer]:
    agent: pydantic_ai.Agent[AgentDeps, AgentAnswer] = pydantic_ai.Agent(
        model,
        deps_type=AgentDeps,
        output_type=AgentAnswer,
        instructions=INSTRUCTIONS,
    )

    @agent.tool
    async def find_fields(
        ctx: pydantic_ai.RunContext[AgentDeps], patterns: list[str], explore_name: str | None = None
    ) -> str:
        """Search explores and fields by keyword patterns. Use `|` to OR synonyms."""
        logger.info("tool find_fields patterns=%s explore=%s", patterns, explore_name)
        await _announce(deps=ctx.deps, step="Searching fields…")
        arguments: dict[str, object] = {
            "projectUuid": ctx.deps.settings.project_uuid,
            "patterns": patterns,
        }
        if explore_name is not None:
            arguments["exploreName"] = explore_name
        raw = await mcp_client.call_tool_raw(
            client=ctx.deps.client, name="grep_fields", arguments=arguments
        )
        return _text_of(raw)

    @agent.tool
    async def run_query(
        ctx: pydantic_ai.RunContext[AgentDeps],
        artifact_id: str,
        title: str,
        description: str,
        query_config: query_spec.QuerySpec,
        chart_config: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """
        Run a governed metric query. artifact_id is "new" or an existing id.
        chart_config may set defaultVizType (table, bar, horizontal, line, scatter, pie, funnel),
        xAxisDimension, yAxisMetrics, xAxisLabel and yAxisLabel.
        """
        logger.info(
            "tool run_query artifact=%s title=%r query=%s chart=%s",
            artifact_id, title, query_config.to_mcp(), chart_config,
        )
        await _announce(deps=ctx.deps, step="Running query…")
        chart_config = chart_config_module.normalize(chart_config=chart_config)
        mcp_query_config = query_config.to_mcp()
        arguments: Mapping[str, object] = {
            "title": title,
            "description": description,
            "queryConfig": mcp_query_config,
            "chartConfig": chart_config,
        }
        result = await queries.run_metric_query(
            client=ctx.deps.client,
            project_uuid=ctx.deps.settings.project_uuid,
            agent_uuid=ctx.deps.settings.agent_uuid,
            arguments=arguments,
        )
        resolved_id = str(uuid.uuid4()) if artifact_id == artifacts.NEW_ARTIFACT else artifact_id
        version = artifacts.next_version(
            existing=_stored_versions(deps=ctx.deps), artifact_id=resolved_id
        )
        ctx.deps.chart_blocks.append(
            blocks.ChartBlock(
                artifact_id=resolved_id,
                version=version,
                title=title,
                query_uuid=result.query_uuid,
                query_args={
                    "title": title,
                    "description": description,
                    "queryConfig": mcp_query_config,
                    "chartConfig": chart_config,
                },
                rows=[dict(row) for row in result.rows],
                fields=dict(result.fields),
                explore_url=result.explore_url,
            )
        )
        return summary.summarize_for_llm(result=result, artifact_id=resolved_id, version=version)

    return agent


def _stored_versions(*, deps: AgentDeps) -> list[artifacts.ArtifactVersion]:
    from lightdash_companion_integration_spike.storage import sqlite

    saved = sqlite.list_artifact_versions(connection=deps.connection, thread_id=deps.thread_id)
    pending = [
        artifacts.ArtifactVersion(
            artifact_id=block.artifact_id,
            version=block.version,
            title=block.title,
            query_args=block.query_args,
        )
        for block in deps.chart_blocks
    ]
    return [*saved, *pending]


def _text_of(raw: object) -> str:
    return "\n".join(block.text for block in raw.content if block.type == "text")  # type: ignore[attr-defined]  # fastmcp result blocks are a union; only text blocks carry .text
