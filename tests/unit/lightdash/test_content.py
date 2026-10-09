import pytest

from lightdash_companion_integration_spike.lightdash import content

QUERY = {
    "exploreName": "orders",
    "dimensions": ["orders_status"],
    "metrics": ["orders_total"],
    "sorts": [{"fieldId": "orders_total", "descending": True}],
    "limit": 10,
}


class TestSlugify:
    def test_lowercases_and_hyphenates_the_title_then_adds_the_suffix(self) -> None:
        assert content.slugify(title="Avg time / by Status!", unique_suffix="abcdef123456") == (
            "avg-time-by-status-abcdef12"
        )

    def test_falls_back_to_chart_when_the_title_has_no_usable_characters(self) -> None:
        assert content.slugify(title="???", unique_suffix="abcdef12") == "chart-abcdef12"


class TestBuildBarChartContent:
    def test_places_the_chart_in_the_requested_space_with_its_query(self) -> None:
        built = content.build_bar_chart_content(
            title="T", description="D", slug="t-1", space_slug="sandbox", query_config=QUERY
        )

        assert (built["spaceSlug"], built["tableName"], built["slug"]) == ("sandbox", "orders", "t-1")
        assert built["metricQuery"] == {
            "exploreName": "orders",
            "dimensions": ["orders_status"],
            "metrics": ["orders_total"],
            "filters": {},
            "sorts": [{"fieldId": "orders_total", "descending": True}],
            "tableCalculations": [],
            "limit": 10,
        }

    def test_is_never_marked_verified(self) -> None:
        built = content.build_bar_chart_content(
            title="T", description="D", slug="t-1", space_slug="sandbox", query_config=QUERY
        )

        assert built["verified"] is False

    def test_uses_the_dimension_on_x_and_the_metric_on_y(self) -> None:
        built = content.build_bar_chart_content(
            title="T", description="D", slug="t-1", space_slug="sandbox", query_config=QUERY
        )

        layout = built["chartConfig"]["config"]["layout"]  # type: ignore[index]  # nested dict built above
        assert layout == {"xField": "orders_status", "yField": ["orders_total"]}

    def test_refuses_a_query_with_more_than_one_dimension(self) -> None:
        with pytest.raises(content.UnsupportedChartShape) as raised:
            content.build_bar_chart_content(
                title="T",
                description="D",
                slug="t-1",
                space_slug="sandbox",
                query_config={**QUERY, "dimensions": ["a", "b"]},
            )

        assert raised.value.dimensions == ["a", "b"]


SUCCESS_TEXT = """<chart href="/projects/p/saved/ffb77177-66c3-44bd-9c68-49c4f550f4fa/view#chart-link" />
---
{"name": "x"}"""


class TestParseSavedChart:
    def test_reads_the_link_and_chart_uuid_from_a_successful_save(self) -> None:
        saved = content.parse_saved_chart(text=SUCCESS_TEXT)

        assert saved == content.SavedChart(
            href="/projects/p/saved/ffb77177-66c3-44bd-9c68-49c4f550f4fa/view#chart-link",
            uuid="ffb77177-66c3-44bd-9c68-49c4f550f4fa",
        )

    def test_raises_when_the_response_has_no_chart_link(self) -> None:
        with pytest.raises(content.SaveReturnedNoLink):
            content.parse_saved_chart(text="something unexpected")
