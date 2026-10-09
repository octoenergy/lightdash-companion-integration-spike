from collections.abc import Mapping

from lightdash_companion_integration_spike.lightdash import queries

SAMPLE_ROW_COUNT = 3


def summarize_for_llm(*, result: queries.QueryResult, artifact_id: str, version: int) -> dict[str, object]:
    """
    Describe a query result to the model without handing it the rows.

    The full rows go to the UI; keeping them out of the context limits what the model can
    leak or be confused by.
    """
    return {
        "artifact_id": artifact_id,
        "version": version,
        "query_uuid": result.query_uuid,
        "row_count": len(result.rows),
        "columns": list(result.fields),
        "sample_rows": [dict(row) for row in result.rows[:SAMPLE_ROW_COUNT]],
        "note": "The user can already see the full chart and table. Do not repeat every row.",
    }


def build_field_request(*, field_ids_by_explore: Mapping[str, list[str]]) -> list[dict[str, object]]:
    """
    Build the tagged `get_metadata` requests the MCP expects.
    """
    return [
        {
            "type": "field",
            "fields": [{"exploreId": explore, "fieldId": field_id} for field_id in field_ids],
        }
        for explore, field_ids in field_ids_by_explore.items()
    ]
