import json
import pathlib

from lightdash_companion_integration_spike.domain import blocks

FIXTURE = pathlib.Path(__file__).parents[2] / "fixtures" / "run_metric_query_result.json"


class TestBlockList:
    def test_round_trips_a_chart_block_built_from_a_real_query_result(self) -> None:
        result = json.loads(FIXTURE.read_text())
        chart = blocks.ChartBlock(
            artifact_id="a",
            version=1,
            title="Avg execution time by status",
            query_uuid=result["queryUuid"],
            query_args={"exploreName": "fct_dbt_runs"},
            rows=result["rows"],
            fields=result["fields"],
            explore_url=result["exploreUrl"],
        )

        restored = blocks.BlockList.validate_python(blocks.BlockList.dump_python([chart]))

        assert restored == [chart]
