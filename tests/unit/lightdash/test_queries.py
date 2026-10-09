import json
import pathlib

import pytest

from lightdash_companion_integration_spike.lightdash import queries

FIXTURE = pathlib.Path(__file__).parents[2] / "fixtures" / "run_metric_query_result.json"


class TestParseResult:
    def test_returns_rows_and_fields_for_a_finished_query(self) -> None:
        done = json.loads(FIXTURE.read_text())

        result = queries.parse_result(structured_content={"result": done})

        assert isinstance(result, queries.QueryResult)
        assert result.query_uuid == "1ca36324-e6d1-46ad-a917-b72d65667d82"
        assert [row["fct_dbt_runs_dbt_run_status"] for row in result.rows] == [
            "partial success",
            "fail",
            "success",
            "skipped",
        ]
        assert sorted(result.fields) == [
            "fct_dbt_runs_avg_execution_time",
            "fct_dbt_runs_dbt_run_status",
        ]

    def test_returns_a_running_marker_with_the_poll_delay(self) -> None:
        running = {"status": "running", "queryUuid": "q", "nextPollAfterMs": 250}

        result = queries.parse_result(structured_content={"result": running})

        assert result == queries.RunningQuery(query_uuid="q", poll_after_ms=250)

    @pytest.mark.parametrize("status", ["error", "cancelled", "expired"])
    def test_raises_for_a_query_that_did_not_finish(self, status: str) -> None:
        failed = {"status": status, "queryUuid": "q", "error": "boom"}

        with pytest.raises(queries.QueryFailed) as raised:
            queries.parse_result(structured_content={"result": failed})

        assert (raised.value.status, raised.value.error) == (status, "boom")

    def test_raises_with_the_server_message_when_there_is_no_structured_result(self) -> None:
        with pytest.raises(queries.MissingStructuredResult) as raised:
            queries.parse_result(structured_content=None, text="MCP error: bad input")

        assert raised.value.server_message == "MCP error: bad input"
