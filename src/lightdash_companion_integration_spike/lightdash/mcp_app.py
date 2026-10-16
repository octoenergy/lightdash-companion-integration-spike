from collections.abc import Mapping

from fastmcp import Client
from mcp import types

from lightdash_companion_integration_spike.agent import chart_config as chart_config_module
from lightdash_companion_integration_spike.lightdash import mcp_client

RENDER_CHART_TOOL = "render_chart"
UI_RESOURCE_URI = "ui://render-chart/chart.html"


class MissingAppHtml(Exception):
    """
    The server's MCP App resource had no HTML text.
    """


async def read_html(*, client: Client) -> str:
    """
    Fetch the HTML bundle that an MCP Apps host mounts in an iframe to draw `render_chart`.
    """
    contents = await client.read_resource(UI_RESOURCE_URI)
    for item in contents:
        if isinstance(item, types.TextResourceContents) and item.text:
            return item.text
    raise MissingAppHtml(UI_RESOURCE_URI)


async def render_chart(
    *,
    client: Client,
    scope: Mapping[str, str],
    query_uuid: str,
    title: str,
    description: str,
    chart_config: Mapping[str, object] | None,
) -> dict[str, object]:
    """
    Call `render_chart` and return the whole tool result for the MCP App to consume.

    The rows the app draws are in `_meta`, not `structuredContent`, so the result is passed on whole.
    """
    arguments: dict[str, object] = {**scope, "queryUuid": query_uuid, "title": title, "description": description}
    normalized = chart_config_module.normalize(chart_config=chart_config)
    if normalized is not None:
        arguments["chartConfig"] = normalized
    raw = await mcp_client.call_tool_raw(client=client, name=RENDER_CHART_TOOL, arguments=arguments)
    return raw.model_dump(by_alias=True, exclude_none=True, mode="json")
