import logging
import re

from fastmcp import Client
from mcp import types

logger = logging.getLogger(__name__)

PROMPT_NAME = "lightdash-analyst"

# Tools the spike agent does not expose; their guidance would make the model call tools it lacks.
UNAVAILABLE_TOOLS = ("run_sql", "render_chart", "list_content", "get_context", "get_query_result")


class AnalystPromptEmpty(Exception):
    """
    The server returned no text for its analyst prompt.
    """


async def fetch(*, client: Client) -> str:
    """
    Fetch the server's own guidance for a model calling its tools.

    Sends an empty arguments object: fastmcp's get_prompt sends none, which this server rejects.
    """
    result = await client.session.get_prompt(PROMPT_NAME, arguments={})
    text = "\n".join(
        message.content.text
        for message in result.messages
        if isinstance(message.content, types.TextContent)
    )
    if not text.strip():
        raise AnalystPromptEmpty()
    return text


def adapt(*, prompt: str) -> str:
    """
    Remove lines that tell the model to use tools this agent does not have.
    """
    kept = [
        line
        for line in prompt.splitlines()
        if not any(re.search(rf"`{tool}`", line) for tool in UNAVAILABLE_TOOLS)
    ]
    return "\n".join(kept)


async def fetch_adapted_or_none(*, client: Client) -> str | None:
    """
    Fetch and adapt the server's guidance, or return None if it cannot be had.

    A missing prompt must not stop the chat: the agent still has its own rules.
    """
    try:
        return adapt(prompt=await fetch(client=client))
    except Exception as error:  # noqa: BLE001 - any failure here is non-fatal
        logger.warning("Could not load the server's analyst prompt: %r", error)
        return None
