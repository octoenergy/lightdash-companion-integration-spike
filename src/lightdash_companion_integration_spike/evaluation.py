from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

import attrs

from lightdash_companion_integration_spike.domain import blocks

CHART = "chart"
DECLINE = "decline"
ARGUMENT_PREVIEW_LENGTH = 160


@attrs.frozen
class Case:
    id: str
    turns: tuple[str, ...]
    expect: Literal["chart", "decline"] = "chart"
    needs_filter: bool = False
    metric_hint: str | None = None


@attrs.frozen
class ToolCall:
    name: str
    arguments: Mapping[str, object]


def flag_problems(
    *,
    case: Case,
    charts: Sequence[blocks.ChartBlock],
    error: str | None,
) -> list[str]:
    """
    Return what is wrong with a run, or an empty list if it met the case's expectation.

    This only checks what can be decided mechanically. Whether the metric was the *right* one
    still needs a person reading the printed queries.
    """
    if error is not None:
        return [f"run failed: {error}"]
    if case.expect == DECLINE:
        return ["answered an unanswerable question"] if charts else []

    problems: list[str] = []
    if not charts:
        return ["no chart produced"]
    if case.needs_filter and not any(_has_filters(chart) for chart in charts):
        problems.append("time-bound question answered without a filter")
    if case.metric_hint and not any(_uses_metric(chart, case.metric_hint) for chart in charts):
        problems.append(f"no metric matching {case.metric_hint!r}")
    return problems


def _query_config(chart: blocks.ChartBlock) -> Mapping[str, object]:
    config = chart.query_args.get("queryConfig", {})
    return config if isinstance(config, dict) else {}


def _has_filters(chart: blocks.ChartBlock) -> bool:
    filters = _query_config(chart).get("filters")
    return bool(filters) and filters != {"type": "and"}


def _uses_metric(chart: blocks.ChartBlock, hint: str) -> bool:
    metrics = _query_config(chart).get("metrics", [])
    return any(hint in str(metric) for metric in metrics)  # type: ignore[attr-defined]  # metrics is a list from our QuerySpec


def describe_query(chart: blocks.ChartBlock) -> str:
    config = _query_config(chart)
    return (
        f"{config.get('exploreName')} | dims={config.get('dimensions')} "
        f"| metrics={config.get('metrics')} | filters={'yes' if _has_filters(chart) else 'no'} "
        f"| rows={len(chart.rows)}"
    )


def tool_names(*, calls: Iterable[ToolCall]) -> list[str]:
    return [call.name for call in calls]


def preview(*, call: ToolCall) -> str:
    text = f"{call.name}({dict(call.arguments)})"
    return text if len(text) <= ARGUMENT_PREVIEW_LENGTH else text[: ARGUMENT_PREVIEW_LENGTH - 1] + "…"


CASES: tuple[Case, ...] = (
    Case("known-good", ("What is the average dbt execution time by run status?",), metric_hint="avg_execution_time"),
    Case("single-value", ("How many active supply points are there?",), metric_hint="supply_points"),
    Case(
        "relative-date",
        ("How many dbt runs failed in the last 7 days, by day?",),
        needs_filter=True,
        metric_hint="runs",
    ),
    # The only matching metric is pre-aggregated weekly, so a daily answer is not possible;
    # declining is correct. Revisit if a daily metric is added.
    Case("yesterday", ("Number of active supply points across all clients yesterday",), expect=DECLINE),
    Case("time-series", ("Show the weekly count of active supply points over the last 8 weeks",), needs_filter=True),
    Case("by-client", ("Which clients have the most errored or failed dbt runs?",), metric_hint="runs"),
    Case("different-domain", ("What is the average inbound call wait time by week?",), metric_hint="wait"),
    Case(
        "follow-up",
        (
            "What is the average dbt execution time by run status?",
            "Now split that by month of creation",
        ),
        metric_hint="avg_execution_time",
    ),
    Case("unanswerable", ("How many unicorns did we ship to Mars last year?",), expect=DECLINE),
    Case("ambiguous", ("How are we doing?",), expect=DECLINE),
)
