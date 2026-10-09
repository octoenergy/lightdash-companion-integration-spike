import json
import pathlib

from lightdash_companion_integration_spike.agent import discovery

FIXTURE = pathlib.Path(__file__).parents[2] / "fixtures" / "get_metadata_result.json"


class TestRequests:
    def test_tags_an_explore_request(self) -> None:
        assert discovery.explore_requests(explore_ids=["a", "b"]) == [
            {"type": "explore", "exploreIds": ["a", "b"]}
        ]

    def test_tags_a_field_request_with_explore_and_field_ids(self) -> None:
        assert discovery.field_requests(fields=[("e", "f")]) == [
            {"type": "field", "fields": [{"exploreId": "e", "fieldId": "f"}]}
        ]


class TestFormatMetadata:
    def test_states_the_explore_description_and_its_field_ids(self) -> None:
        metadata = json.loads(FIXTURE.read_text())

        text = discovery.format_metadata(metadata=metadata)

        assert "Count of supply points that are active on kraken in this week" in text
        assert "union_count_supply_points_per_kpi_week_week_start_date" in text

    def test_keeps_a_metric_description_that_limits_its_grain(self) -> None:
        metadata = json.loads(FIXTURE.read_text())

        text = discovery.format_metadata(metadata=metadata)

        assert "cannot be rolled up or broken down further into finer timeframes" in text

    def test_reports_an_explore_that_does_not_exist(self) -> None:
        text = discovery.format_metadata(
            metadata={"explores": [{"exploreId": "nope", "status": "notFound"}], "fields": []}
        )

        assert text == "Explore nope: not found"

    def test_clips_very_long_descriptions(self) -> None:
        metadata = {
            "explores": [
                {"exploreId": "e", "status": "found", "description": "x" * 5000, "baseDimensions": {}, "baseMetrics": {}}
            ],
            "fields": [],
        }

        text = discovery.format_metadata(metadata=metadata)

        assert len(text) < discovery.DESCRIPTION_LENGTH + 100

    def test_flags_required_filters(self) -> None:
        metadata = {
            "explores": [
                {"exploreId": "e", "status": "found", "description": "d", "requiredFilters": [{"field": "x"}],
                 "baseDimensions": {}, "baseMetrics": {}}
            ],
            "fields": [],
        }

        assert "REQUIRED FILTERS" in discovery.format_metadata(metadata=metadata)


class TestParseValueSearch:
    def test_reads_matching_values_from_the_fenced_json_block(self) -> None:
        text = '```json\n{"search": "talk", "results": ["talktalk-kap-prod"], "cached": false}\n```'

        assert discovery.parse_value_search(text=text) == ["talktalk-kap-prod"]

    def test_returns_no_values_for_an_error_message(self) -> None:
        text = "Error searching field values.\n\n```\nListing all values is disabled\n```"

        assert discovery.parse_value_search(text=text) == []

    def test_returns_no_values_when_nothing_matched(self) -> None:
        assert discovery.parse_value_search(text='```json\n{"results": []}\n```') == []
