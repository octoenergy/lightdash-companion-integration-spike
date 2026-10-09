from lightdash_companion_integration_spike.agent import summary
from lightdash_companion_integration_spike.lightdash import queries


def _result(row_count: int) -> queries.QueryResult:
    return queries.QueryResult(
        query_uuid="q",
        rows=tuple({"status": f"s{index}", "n": index} for index in range(row_count)),
        fields={"status": {}, "n": {}},
        explore_url=None,
    )


class TestSummarizeForLlm:
    def test_reports_row_count_but_only_a_sample_of_rows(self) -> None:
        described = summary.summarize_for_llm(result=_result(10), artifact_id="a", version=2)

        assert described["row_count"] == 10
        assert described["sample_rows"] == [
            {"status": "s0", "n": 0},
            {"status": "s1", "n": 1},
            {"status": "s2", "n": 2},
        ]

    def test_names_the_columns_and_the_artifact_version(self) -> None:
        described = summary.summarize_for_llm(result=_result(1), artifact_id="a", version=2)

        assert (described["columns"], described["artifact_id"], described["version"]) == (
            ["status", "n"],
            "a",
            2,
        )


class TestBuildFieldRequest:
    def test_tags_each_explore_as_a_field_request(self) -> None:
        requests = summary.build_field_request(field_ids_by_explore={"orders": ["a", "b"]})

        assert requests == [
            {
                "type": "field",
                "fields": [
                    {"exploreId": "orders", "fieldId": "a"},
                    {"exploreId": "orders", "fieldId": "b"},
                ],
            }
        ]
