from lightdash_companion_integration_spike import evaluation
from lightdash_companion_integration_spike.domain import blocks


def _chart(*, metrics: list[str], filters: dict[str, object] | None = None) -> blocks.ChartBlock:
    query_config: dict[str, object] = {"exploreName": "e", "dimensions": [], "metrics": metrics}
    if filters is not None:
        query_config["filters"] = filters
    return blocks.ChartBlock(
        artifact_id="a",
        version=1,
        title="t",
        query_uuid="q",
        query_args={"queryConfig": query_config},
        rows=[],
        fields={},
    )


CHART_CASE = evaluation.Case("c", ("q",), metric_hint="supply_points")


class TestFlagProblems:
    def test_passes_a_chart_that_uses_the_expected_metric(self) -> None:
        problems = evaluation.flag_problems(
            case=CHART_CASE, charts=[_chart(metrics=["x_active_supply_points"])], error=None
        )

        assert problems == []

    def test_reports_a_run_that_failed(self) -> None:
        problems = evaluation.flag_problems(case=CHART_CASE, charts=[], error="boom")

        assert problems == ["run failed: boom"]

    def test_reports_when_no_chart_was_produced_for_an_answerable_question(self) -> None:
        assert evaluation.flag_problems(case=CHART_CASE, charts=[], error=None) == ["no chart produced"]

    def test_reports_a_metric_that_does_not_match_the_hint(self) -> None:
        problems = evaluation.flag_problems(
            case=CHART_CASE, charts=[_chart(metrics=["something_else"])], error=None
        )

        assert problems == ["no metric matching 'supply_points'"]

    def test_reports_a_time_bound_question_answered_without_a_filter(self) -> None:
        case = evaluation.Case("c", ("q",), needs_filter=True)

        problems = evaluation.flag_problems(case=case, charts=[_chart(metrics=["m"])], error=None)

        assert problems == ["time-bound question answered without a filter"]

    def test_accepts_a_time_bound_question_that_was_filtered(self) -> None:
        case = evaluation.Case("c", ("q",), needs_filter=True)
        filtered = _chart(metrics=["m"], filters={"type": "and", "dimensions": [{"fieldId": "d"}]})

        assert evaluation.flag_problems(case=case, charts=[filtered], error=None) == []

    def test_an_empty_filter_group_does_not_count_as_a_filter(self) -> None:
        case = evaluation.Case("c", ("q",), needs_filter=True)

        problems = evaluation.flag_problems(
            case=case, charts=[_chart(metrics=["m"], filters={"type": "and"})], error=None
        )

        assert problems == ["time-bound question answered without a filter"]


class TestDeclineCases:
    def test_passes_when_the_agent_declines(self) -> None:
        case = evaluation.Case("c", ("q",), expect=evaluation.DECLINE)

        assert evaluation.flag_problems(case=case, charts=[], error=None) == []

    def test_reports_an_invented_answer(self) -> None:
        case = evaluation.Case("c", ("q",), expect=evaluation.DECLINE)

        problems = evaluation.flag_problems(case=case, charts=[_chart(metrics=["m"])], error=None)

        assert problems == ["answered an unanswerable question"]


class TestPreview:
    def test_truncates_long_arguments(self) -> None:
        call = evaluation.ToolCall(name="run_query", arguments={"q": "x" * 500})

        assert len(evaluation.preview(call=call)) == evaluation.ARGUMENT_PREVIEW_LENGTH
