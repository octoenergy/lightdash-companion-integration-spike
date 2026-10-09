"""
End-to-end check: ask the agent a question against the live MCP.

Run with: uv run python scripts/ask_agent.py "your question"
"""

import asyncio
import os
import sys

from lightdash_companion_integration_spike import config
from lightdash_companion_integration_spike.agent import agent as agent_module
from lightdash_companion_integration_spike.agent import history
from lightdash_companion_integration_spike.domain import blocks
from lightdash_companion_integration_spike.lightdash import mcp_client
from lightdash_companion_integration_spike.storage import sqlite


async def turn(*, settings, client, connection, thread_id: str, question: str) -> agent_module.AgentDeps:
    stored = sqlite.list_messages(connection=connection, thread_id=thread_id)
    existing = sqlite.list_artifact_versions(connection=connection, thread_id=thread_id)
    deps = agent_module.AgentDeps(settings=settings, client=client, connection=connection, thread_id=thread_id)
    result = await agent_module.build_agent().run(
        question,
        deps=deps,
        message_history=history.build_message_history(stored=stored, existing_artifacts=existing),
    )
    sqlite.add_message(connection=connection, thread_id=thread_id, role=sqlite.USER_ROLE, text=question, message_blocks=[blocks.MarkdownBlock(text=question)])
    message_id = sqlite.add_message(connection=connection, thread_id=thread_id, role=sqlite.ASSISTANT_ROLE, text=result.output.text, message_blocks=[blocks.MarkdownBlock(text=result.output.text), *deps.chart_blocks])
    for block in deps.chart_blocks:
        sqlite.save_artifact_version(connection=connection, thread_id=thread_id, artifact_id=block.artifact_id, title=block.title, query_args=block.query_args, message_id=message_id)
    print("Q:", question)
    for block in deps.chart_blocks:
        print("  chart:", block.title, "| artifact", block.artifact_id[:8], "v", block.version, "| dims", block.query_args["queryConfig"]["dimensions"])
    return deps


async def main(question: str) -> None:
    settings = config.load_settings()
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key or ""
    connection = sqlite.connect(path=":memory:")
    thread_id = sqlite.create_thread(connection=connection, title=question)

    async def on_step(step: str) -> None:
        print("  step:", step)

    async with mcp_client.create_client(settings=settings, token=settings.lightdash_token) as client:
        deps = agent_module.AgentDeps(
            settings=settings,
            client=client,
            connection=connection,
            thread_id=thread_id,
            on_step=on_step,
        )
        result = await agent_module.build_agent().run(question, deps=deps)

    print("answer:", result.output.text)
    print("follow_ups:", result.output.follow_ups)
    for block in deps.chart_blocks:
        print("chart:", block.title, "| rows:", len(block.rows), "| artifact:", block.artifact_id[:8], "v", block.version)


asyncio.run(main(" ".join(sys.argv[1:]) or "What is the average dbt execution time by run status?"))
