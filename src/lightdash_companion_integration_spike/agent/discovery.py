import json
import re
from collections.abc import Mapping, Sequence

DESCRIPTION_LENGTH = 400
MAX_FIELDS_PER_KIND = 40

Metadata = Mapping[str, object]


def explore_requests(*, explore_ids: Sequence[str]) -> list[dict[str, object]]:
    """
    Build the tagged `get_metadata` request for whole explores.
    """
    return [{"type": "explore", "exploreIds": list(explore_ids)}]


def field_requests(*, fields: Sequence[tuple[str, str]]) -> list[dict[str, object]]:
    """
    Build the tagged `get_metadata` request for specific (explore, field id) pairs.
    """
    return [
        {
            "type": "field",
            "fields": [{"exploreId": explore, "fieldId": field_id} for explore, field_id in fields],
        }
    ]


def _clip(text: object) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= DESCRIPTION_LENGTH else value[: DESCRIPTION_LENGTH - 1] + "…"


def _field_ids(group: object) -> list[str]:
    if isinstance(group, dict):
        return [str(field_id) for field_id in group.get("fieldIds", [])]
    return []


def format_metadata(*, metadata: Metadata) -> str:
    """
    Describe explores and fields as compact text for the model.

    Keeps what decides whether an explore fits a question: what each row is, required filters, and
    each field's own description (which states grain and limits, e.g. "cannot be broken down finer").
    """
    sections: list[str] = []
    for explore in metadata.get("explores", []):  # type: ignore[attr-defined]  # metadata comes straight from the MCP payload
        if not isinstance(explore, dict):
            continue
        if explore.get("status") != "found":
            sections.append(f"Explore {explore.get('exploreId')}: not found")
            continue
        lines = [f"Explore {explore['exploreId']}: {_clip(explore.get('description'))}"]
        if explore.get("requiredFilters"):
            lines.append(f"  REQUIRED FILTERS: {explore['requiredFilters']}")
        for label, key in (("Dimensions", "baseDimensions"), ("Metrics", "baseMetrics")):
            ids = _field_ids(explore.get(key))
            shown = ids[:MAX_FIELDS_PER_KIND]
            suffix = f" (+{len(ids) - len(shown)} more)" if len(ids) > len(shown) else ""
            lines.append(f"  {label}: {', '.join(shown)}{suffix}")
        sections.append("\n".join(lines))

    for field in metadata.get("fields", []):  # type: ignore[attr-defined]  # metadata comes straight from the MCP payload
        if not isinstance(field, dict) or field.get("status") != "found":
            continue
        sections.append(
            f"Field {field['fieldId']} [{field.get('kind')} {field.get('fieldType')}] "
            f"\"{field.get('label')}\": {_clip(field.get('description'))}"
        )
    return "\n\n".join(sections)


JSON_BLOCK_PATTERN = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


def parse_value_search(*, text: str) -> list[str]:
    """
    Read matching values out of a `search_field_values` response.

    The server returns the result as a fenced JSON block in text, not as structured content. An
    error comes back as plain text, which yields no values.
    """
    block = JSON_BLOCK_PATTERN.search(text)
    if block is None:
        return []
    try:
        payload = json.loads(block.group(1))
    except json.JSONDecodeError:
        return []
    return [str(value) for value in payload.get("results", [])]
