from lightdash_companion_integration_spike.domain import filters, query_spec


class TestQuerySpecToMcp:
    def test_uses_the_camel_case_keys_the_server_expects(self) -> None:
        spec = query_spec.QuerySpec(
            explore_name="orders",
            dimensions=["orders_status"],
            metrics=["orders_total"],
            sorts=[query_spec.Sort(field_id="orders_total", descending=True)],
        )

        assert spec.to_mcp() == {
            "exploreName": "orders",
            "dimensions": ["orders_status"],
            "metrics": ["orders_total"],
            "sorts": [{"fieldId": "orders_total", "descending": True}],
            "filters": None,
            "limit": 500,
        }

    def test_sends_filters_in_the_servers_rule_shape(self) -> None:
        spec = query_spec.QuerySpec(
            explore_name="orders",
            dimensions=["orders_day"],
            metrics=["orders_total"],
            filters=[filters.InThePast(field_id="orders_day", count=7, unit="days")],
        )

        sent = spec.to_mcp()["filters"]

        assert sent["type"] == "and"  # type: ignore[index]  # filters is a dict when present
        assert sent["dimensions"][0]["operator"] == "inThePast"  # type: ignore[index]  # filters is a dict when present
