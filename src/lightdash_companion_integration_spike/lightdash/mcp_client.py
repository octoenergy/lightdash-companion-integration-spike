from collections.abc import Mapping

from fastmcp import Client
from fastmcp.client import transports
from mcp import types

from lightdash_companion_integration_spike import config
from lightdash_companion_integration_spike.lightdash import user_attributes

MCP_TIMEOUT_SECONDS = 60


def mcp_url(*, settings: config.Settings) -> str:
    return f"{settings.lightdash_url.rstrip('/')}/api/v1/mcp/projects/{settings.project_uuid}"


def build_headers(
    *,
    token: str,
    attributes: Mapping[str, user_attributes.AttributeValue] | None = None,
) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if attributes is not None:
        headers.update(user_attributes.build_header(attributes=attributes))
    return headers


def create_client(
    *,
    settings: config.Settings,
    token: str,
    attributes: Mapping[str, user_attributes.AttributeValue] | None = None,
) -> Client:
    transport = transports.StreamableHttpTransport(
        url=mcp_url(settings=settings),
        headers=build_headers(token=token, attributes=attributes),
    )
    return Client(transport, timeout=MCP_TIMEOUT_SECONDS)


async def call_tool_raw(
    *, client: Client, name: str, arguments: Mapping[str, object]
) -> types.CallToolResult:
    """
    Call a tool and return the unprocessed MCP result.

    The raw result keeps `structuredContent` and `_meta`, which the higher-level
    fastmcp result drops or reshapes.
    """
    return await client.call_tool_mcp(name, dict(arguments))
