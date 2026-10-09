import asyncio
import logging
from collections.abc import Mapping

import attrs
from fastmcp import Client
from mcp import types

from lightdash_companion_integration_spike.lightdash import mcp_client

logger = logging.getLogger(__name__)

MAX_POLLS = 30
DEFAULT_POLL_DELAY_MS = 1000
MS_PER_SECOND = 1000


class QueryFailed(Exception):
    def __init__(self, *, status: str, query_uuid: str | None, error: str | None) -> None:
        super().__init__(status)
        self.status = status
        self.query_uuid = query_uuid
        self.error = error


class QueryStillRunning(Exception):
    def __init__(self, *, query_uuid: str) -> None:
        super().__init__(query_uuid)
        self.query_uuid = query_uuid


class MissingStructuredResult(Exception):
    """
    The MCP response had no `structuredContent.result`, usually because the server rejected the call.
    """

    def __init__(self, *, server_message: str | None = None) -> None:
        super().__init__(server_message)
        self.server_message = server_message


@attrs.frozen
class QueryResult:
    query_uuid: str
    rows: tuple[Mapping[str, object], ...]
    fields: Mapping[str, object]
    explore_url: str | None


@attrs.frozen
class RunningQuery:
    query_uuid: str
    poll_after_ms: int


def parse_result(
    *,
    structured_content: Mapping[str, object] | None,
    text: str | None = None,
) -> QueryResult | RunningQuery:
    """
    Turn a `run_metric_query` or `get_query_result` payload into a result or a running marker.

    Raises QueryFailed for error, cancelled and expired queries.
    """
    result = (structured_content or {}).get("result")
    if not isinstance(result, dict):
        raise MissingStructuredResult(server_message=text)

    status = result.get("status")
    query_uuid = result.get("queryUuid")
    if status == "done":
        return QueryResult(
            query_uuid=str(query_uuid),
            rows=tuple(result.get("rows", [])),
            fields=dict(result.get("fields", {})),
            explore_url=result.get("exploreUrl"),
        )
    if status == "running":
        return RunningQuery(
            query_uuid=str(query_uuid),
            poll_after_ms=int(result.get("nextPollAfterMs", DEFAULT_POLL_DELAY_MS)),
        )
    raise QueryFailed(
        status=str(status),
        query_uuid=str(query_uuid) if query_uuid else None,
        error=result.get("error"),
    )


async def run_metric_query(
    *,
    client: Client,
    project_uuid: str,
    agent_uuid: str | None,
    arguments: Mapping[str, object],
) -> QueryResult:
    """
    Run a governed metric query and poll until it finishes.

    Raises QueryFailed if the query errors, and QueryStillRunning if it outlasts the poll budget.
    """
    scope = _scope(project_uuid=project_uuid, agent_uuid=agent_uuid)
    raw = await mcp_client.call_tool_raw(
        client=client, name="run_metric_query", arguments={**scope, **arguments}
    )
    logger.info("run_metric_query explore=%s", arguments.get("queryConfig", {}).get("exploreName"))  # type: ignore[attr-defined]  # queryConfig is a mapping when present
    try:
        outcome = parse_result(structured_content=raw.structured_content, text=_text_of(raw))
    except MissingStructuredResult as error:
        logger.error("MCP rejected run_metric_query: %s", error.server_message)
        raise

    for _ in range(MAX_POLLS):
        if isinstance(outcome, QueryResult):
            return outcome
        await asyncio.sleep(outcome.poll_after_ms / MS_PER_SECOND)
        raw = await mcp_client.call_tool_raw(
            client=client,
            name="get_query_result",
            arguments={**scope, "queryUuid": outcome.query_uuid},
        )
        outcome = parse_result(structured_content=raw.structured_content, text=_text_of(raw))

    if isinstance(outcome, QueryResult):
        return outcome
    raise QueryStillRunning(query_uuid=outcome.query_uuid)


def _text_of(raw: types.CallToolResult) -> str:
    return "\n".join(block.text for block in raw.content if isinstance(block, types.TextContent))


def _scope(*, project_uuid: str, agent_uuid: str | None) -> dict[str, str]:
    scope = {"projectUuid": project_uuid}
    if agent_uuid is not None:
        scope["agentUuid"] = agent_uuid
    return scope
