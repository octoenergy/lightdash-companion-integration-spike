import re
from collections.abc import Mapping

import attrs
from fastmcp import Client
from mcp import types

from lightdash_companion_integration_spike.lightdash import mcp_client

CONTENT_VERSION = 1
SLUG_SUFFIX_LENGTH = 8
DEFAULT_LIMIT = 500


class SaveRejected(Exception):
    def __init__(self, *, server_message: str) -> None:
        super().__init__(server_message)
        self.server_message = server_message


def slugify(*, title: str, unique_suffix: str) -> str:
    """
    Return a slug that stays unique when the same title is saved more than once.
    """
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "chart"
    return f"{base}-{unique_suffix[:SLUG_SUFFIX_LENGTH]}"


def build_bar_chart_content(
    *,
    title: str,
    description: str,
    slug: str,
    space_slug: str,
    query_config: Mapping[str, object],
) -> dict[str, object]:
    """
    Build chart-as-code JSON for a single-dimension bar chart.

    Every dimension must be used by the layout, otherwise Lightdash adds an unintended GROUP BY,
    so this only supports one dimension on the x axis.
    """
    dimensions = [str(item) for item in query_config.get("dimensions", [])]  # type: ignore[attr-defined]  # query_config comes from our validated QuerySpec
    metrics = [str(item) for item in query_config.get("metrics", [])]  # type: ignore[attr-defined]  # query_config comes from our validated QuerySpec
    if len(dimensions) != 1 or not metrics:
        raise UnsupportedChartShape(dimensions=dimensions, metrics=metrics)

    explore_name = str(query_config["exploreName"])
    return {
        "contentType": "chart",
        "slug": slug,
        "name": title,
        "description": description,
        "spaceSlug": space_slug,
        "tableName": explore_name,
        "version": CONTENT_VERSION,
        "verified": False,
        "dashboardSlug": "",
        "metricQuery": {
            "exploreName": explore_name,
            "dimensions": dimensions,
            "metrics": metrics,
            "filters": {},
            "sorts": query_config.get("sorts", []),
            "tableCalculations": [],
            "limit": query_config.get("limit") or DEFAULT_LIMIT,
        },
        "chartConfig": {
            "type": "cartesian",
            "config": {
                "layout": {"xField": dimensions[0], "yField": metrics},
                "eChartsConfig": {
                    "series": [
                        {
                            "type": "bar",
                            "encode": {
                                "xRef": {"field": dimensions[0]},
                                "yRef": {"field": metric},
                            },
                        }
                        for metric in metrics
                    ]
                },
            },
        },
        "tableConfig": {"columnOrder": [*dimensions, *metrics]},
    }


class UnsupportedChartShape(Exception):
    def __init__(self, *, dimensions: list[str], metrics: list[str]) -> None:
        super().__init__()
        self.dimensions = dimensions
        self.metrics = metrics


@attrs.frozen
class SavedChart:
    href: str
    uuid: str | None


CHART_HREF_PATTERN = re.compile(r'<chart href="([^"]+)"')
CHART_UUID_PATTERN = re.compile(r"/saved/([0-9a-f-]{36})/")


class SaveReturnedNoLink(Exception):
    """
    The server accepted the content but the response had no chart link to parse.
    """


def parse_saved_chart(*, text: str) -> SavedChart:
    """
    Read the new chart's link out of a successful create_content response.

    A successful save carries no structured content: it is a `<chart href="..."/>` tag followed
    by the persisted JSON.
    """
    link = CHART_HREF_PATTERN.search(text)
    if link is None:
        raise SaveReturnedNoLink()
    uuid_match = CHART_UUID_PATTERN.search(link.group(1))
    return SavedChart(href=link.group(1), uuid=uuid_match.group(1) if uuid_match else None)


async def create_chart(
    *,
    client: Client,
    project_uuid: str,
    agent_uuid: str | None,
    content: Mapping[str, object],
) -> SavedChart:
    """
    Save a chart through the MCP and return a link to what Lightdash persisted.

    Raises SaveRejected with the server's message if the content is not accepted.
    """
    arguments: dict[str, object] = {
        "projectUuid": project_uuid,
        "type": "chart",
        "content": dict(content),
    }
    if agent_uuid is not None:
        arguments["agentUuid"] = agent_uuid
    raw = await mcp_client.call_tool_raw(client=client, name="create_content", arguments=arguments)
    text = "\n".join(block.text for block in raw.content if isinstance(block, types.TextContent))
    if raw.is_error:
        raise SaveRejected(server_message=text)
    return parse_saved_chart(text=text)
