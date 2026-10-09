"""
Step 0 probe: show what the KTL Lightdash MCP actually returns.

Run with: uv run python scripts/probe_mcp.py
"""

import asyncio
import json

from lightdash_companion_integration_spike import config
from lightdash_companion_integration_spike.lightdash import mcp_client

PROBE_QUERY = {
    "title": "Average dbt execution time by run status",
    "description": "Spike probe",
    "queryConfig": {
        "exploreName": "fct_dbt_runs",
        "dimensions": ["fct_dbt_runs_dbt_run_status"],
        "metrics": ["fct_dbt_runs_avg_execution_time"],
        "sorts": [{"fieldId": "fct_dbt_runs_avg_execution_time", "descending": True}],
        "limit": 10,
    },
    "chartConfig": {
        "defaultVizType": "bar",
        "xAxisDimension": "fct_dbt_runs_dbt_run_status",
        "yAxisMetrics": ["fct_dbt_runs_avg_execution_time"],
        "xAxisLabel": "Run status",
        "yAxisLabel": "Avg execution time (s)",
    },
}


def describe(label: str, result) -> None:
    structured = result.structured_content or {}
    inner = structured.get("result", structured)
    print(f"{label}:")
    print("  content blocks:", [block.type for block in result.content])
    print("  structured_content keys:", sorted(structured.keys()))
    print("  structuredContent.result keys:", sorted(inner.keys()) if isinstance(inner, dict) else type(inner))
    print("  _meta:", json.dumps(result.meta)[:200] if result.meta else None)
    print("  row count:", len(inner.get("rows", [])) if isinstance(inner, dict) else None)


async def main() -> None:
    settings = config.load_settings()
    client = mcp_client.create_client(settings=settings, token=settings.lightdash_token)
    async with client:
        version = await mcp_client.call_tool_raw(client=client, name="get_lightdash_version", arguments={})
        print("lightdash version:", version.content[0].text)

        query = await mcp_client.call_tool_raw(
            client=client,
            name="run_metric_query",
            arguments={"projectUuid": settings.project_uuid, **PROBE_QUERY},
        )
        describe("run_metric_query", query)


asyncio.run(main())
