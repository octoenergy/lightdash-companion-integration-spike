import jwt

from lightdash_companion_integration_spike.lightdash import embed


class TestBuildJwtPayload:
    def test_allows_exploring_and_carries_user_attributes(self) -> None:
        payload = embed.build_jwt_payload(
            project_uuid="p", user_attributes={"tenant_id": "1"}, now=1000
        )

        assert payload["content"] == {
            "type": "metricsCatalog",
            "projectUuid": "p",
            "canExplore": True,
        }
        assert payload["userAttributes"] == {"tenant_id": "1"}
        assert payload["exp"] == 1000 + embed.EMBED_TOKEN_LIFETIME_SECONDS


class TestBuildExploreUrl:
    def test_puts_chart_in_query_and_token_in_hash(self) -> None:
        token = embed.mint_token(secret="test-secret-that-is-at-least-32-bytes-long", payload={"a": 1})

        url = embed.build_explore_url(
            site_url="https://ld.example.com/",
            project_uuid="p",
            explore_name="orders",
            saved_chart_version={"tableName": "orders"},
            token=token,
        )

        assert url.startswith("https://ld.example.com/embed/p/explore/orders?create_saved_chart_version=")
        assert url.endswith(f"#{token}")
        assert jwt.decode(token, "test-secret-that-is-at-least-32-bytes-long", algorithms=["HS256"]) == {"a": 1}


class TestExploreState:
    def test_carries_the_query_so_the_explore_opens_on_the_same_data(self) -> None:
        state = embed.explore_state(
            explore_name="orders",
            query_config={"dimensions": ["orders_status"], "metrics": ["orders_total"], "limit": 5},
            column_order=["orders_status", "orders_total"],
        )

        assert state["tableName"] == "orders"
        assert state["metricQuery"] == {
            "exploreName": "orders",
            "dimensions": ["orders_status"],
            "metrics": ["orders_total"],
            "filters": {},
            "sorts": [],
            "limit": 5,
            "tableCalculations": [],
        }
