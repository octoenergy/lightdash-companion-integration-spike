from lightdash_companion_integration_spike.domain import query_spec


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
            "limit": 500,
        }
