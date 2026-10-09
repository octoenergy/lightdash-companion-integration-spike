"""
Run the fixed question set against the live agent and print a scorecard.

Run with: uv run python scripts/eval_questions.py [label] [case-id ...]

Each run writes docs/eval/<label>.json so changes to the agent can be compared. Mechanical checks
only flag obvious failures: read the printed queries to judge whether the metric was *right*.
"""

import asyncio
import json
import os
import pathlib
import sys

from lightdash_companion_integration_spike import config, evaluation
from lightdash_companion_integration_spike.agent import agent as agent_module
from lightdash_companion_integration_spike.agent import history
from lightdash_companion_integration_spike.domain import blocks
from lightdash_companion_integration_spike.lightdash import analyst_prompt, mcp_client
from lightdash_companion_integration_spike.storage import sqlite

OUTPUT_DIR = pathlib.Path("docs/eval")
USE_SERVER_PROMPT = os.environ.get("EVAL_SERVER_PROMPT", "1") == "1"


async def run_case(*, case: evaluation.Case, settings: config.Settings) -> dict[str, object]:
    connection = sqlite.connect(path=":memory:")
    thread_id = sqlite.create_thread(connection=connection, title=case.id)
    calls: list[evaluation.ToolCall] = []
    all_charts: list[blocks.ChartBlock] = []
    answers: list[str] = []
    tokens = 0
    error: str | None = None

    try:
        async with mcp_client.create_client(settings=settings, token=settings.lightdash_token) as client:
            guidance = await analyst_prompt.fetch_adapted_or_none(client=client) if USE_SERVER_PROMPT else None
            for question in case.turns:
                deps = agent_module.AgentDeps(
                    settings=settings,
                    client=client,
                    connection=connection,
                    thread_id=thread_id,
                    on_tool_call=lambda name, arguments: calls.append(
                        evaluation.ToolCall(name=name, arguments=arguments)
                    ),
                )
                stored = sqlite.list_messages(connection=connection, thread_id=thread_id)
                existing = sqlite.list_artifact_versions(connection=connection, thread_id=thread_id)
                result = await agent_module.build_agent(server_guidance=guidance).run(
                    question,
                    deps=deps,
                    message_history=history.build_message_history(stored=stored, existing_artifacts=existing),
                )
                tokens += result.usage.total_tokens or 0
                answers.append(result.output.text)
                all_charts.extend(deps.chart_blocks)
                sqlite.add_message(connection=connection, thread_id=thread_id, role=sqlite.USER_ROLE, text=question, message_blocks=[blocks.MarkdownBlock(text=question)])
                message_id = sqlite.add_message(connection=connection, thread_id=thread_id, role=sqlite.ASSISTANT_ROLE, text=result.output.text, message_blocks=[blocks.MarkdownBlock(text=result.output.text), *deps.chart_blocks])
                for chart in deps.chart_blocks:
                    sqlite.save_artifact_version(connection=connection, thread_id=thread_id, artifact_id=chart.artifact_id, title=chart.title, query_args=chart.query_args, message_id=message_id)
    except Exception as exception:  # one failing case must not stop the run
        error = f"{type(exception).__name__}: {str(exception)[:200]}"

    problems = evaluation.flag_problems(case=case, charts=all_charts, error=error)
    return {
        "id": case.id,
        "ok": not problems,
        "problems": problems,
        "tools": evaluation.tool_names(calls=calls),
        "queries": [evaluation.describe_query(chart) for chart in all_charts],
        "answer": answers[-1][:300] if answers else None,
        "tokens": tokens,
    }


async def main(label: str, only: set[str]) -> None:
    settings = config.load_settings()
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key or ""
    results = []
    for case in evaluation.CASES:
        if only and case.id not in only:
            continue
        outcome = await run_case(case=case, settings=settings)
        results.append(outcome)
        print(f"\n[{'PASS' if outcome['ok'] else 'FAIL'}] {case.id}  tokens={outcome['tokens']}")
        print(f"   tools:   {outcome['tools']}")
        for query in outcome["queries"]:
            print(f"   query:   {query}")
        for problem in outcome["problems"]:
            print(f"   problem: {problem}")
        print(f"   answer:  {(outcome['answer'] or '')[:160]}")

    passed = sum(1 for r in results if r["ok"])
    print(f"\n=== {label}: {passed}/{len(results)} passed mechanical checks, {sum(r['tokens'] for r in results)} tokens")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{label}.json").write_text(json.dumps(results, indent=2))


arguments = sys.argv[1:]
asyncio.run(main(arguments[0] if arguments else "baseline", set(arguments[1:])))
