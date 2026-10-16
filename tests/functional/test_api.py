import json
from collections.abc import Iterator
from unittest import mock

import pytest
from fastapi import testclient

from lightdash_companion_integration_spike import config
from lightdash_companion_integration_spike.api import app as app_module
from lightdash_companion_integration_spike.api import routes
from lightdash_companion_integration_spike.lightdash import content, queries
from lightdash_companion_integration_spike.storage import sqlite


class FakeMcpClient:
    async def __aenter__(self) -> "FakeMcpClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


@pytest.fixture(autouse=True)
def offline_mcp_client() -> Iterator[mock.Mock]:
    with mock.patch.object(routes.mcp_client, "create_client", return_value=FakeMcpClient()) as create_client:
        yield create_client


@pytest.fixture
def client() -> Iterator[testclient.TestClient]:
    settings = config.Settings(
        lightdash_url="https://ld.example.com",
        lightdash_token="user-token",
        lightdash_admin_token="admin-token",
        project_uuid="p",
        sandbox_space_slug="sandbox",
    )
    application = app_module.create_app(settings=settings, connection=sqlite.connect(path=":memory:"))
    with testclient.TestClient(application) as test_client:
        yield test_client


class TestThreads:
    def test_a_new_thread_appears_in_the_list(self, client: testclient.TestClient) -> None:
        created = client.post("/api/threads").json()

        listed = client.get("/api/threads").json()

        assert [thread["id"] for thread in listed] == [created["id"]]

    def test_a_new_thread_has_no_messages(self, client: testclient.TestClient) -> None:
        created = client.post("/api/threads").json()

        assert client.get(f"/api/threads/{created['id']}").json() == []


class TestFeedback:
    def test_stores_the_rating_against_the_message(self, client: testclient.TestClient) -> None:
        connection = client.app.state.connection
        thread_id = sqlite.create_thread(connection=connection, title="t")
        message_id = sqlite.add_message(
            connection=connection, thread_id=thread_id, role=sqlite.ASSISTANT_ROLE, text="x", message_blocks=[]
        )

        client.post(f"/api/messages/{message_id}/feedback", json={"rating": "up"})

        assert client.get(f"/api/threads/{thread_id}").json()[0]["feedback"] == "up"


class TestMcpAppHtml:
    @mock.patch.object(routes.mcp_app, "read_html", return_value="<html>app</html>")
    def test_serves_the_servers_app_html_so_the_browser_can_frame_it(
        self, read_html: mock.AsyncMock, client: testclient.TestClient
    ) -> None:
        response = client.get("/api/mcp-app/html")

        assert (response.status_code, response.text) == (200, "<html>app</html>")
        assert response.headers["content-type"].startswith("text/html")


class TestTokenSelection:
    def test_uses_the_admin_token_only_when_narrowing_user_attributes(self) -> None:
        settings = config.Settings(
            lightdash_url="u", lightdash_token="user", lightdash_admin_token="admin", project_uuid="p"
        )

        chosen = [
            routes._token_for(settings=settings, user_attributes=None),
            routes._token_for(settings=settings, user_attributes={"tenant": "1"}),
        ]

        assert chosen == ["user", "admin"]


class TestSaveChart:
    @mock.patch.object(routes.content, "create_chart")
    def test_saves_into_the_configured_sandbox_space_and_returns_a_full_link(
        self, create_chart: mock.AsyncMock, client: testclient.TestClient
    ) -> None:
        create_chart.return_value = content.SavedChart(href="/projects/p/saved/u/view", uuid="u")

        response = client.post(
            "/api/charts/save",
            json={
                "title": "T",
                "query_config": {"exploreName": "orders", "dimensions": ["a"], "metrics": ["b"]},
            },
        )

        assert response.json() == {"href": "https://ld.example.com/projects/p/saved/u/view", "uuid": "u"}
        assert create_chart.call_args.kwargs["content"]["spaceSlug"] == "sandbox"

    def test_refuses_a_chart_with_more_than_one_dimension(self, client: testclient.TestClient) -> None:
        response = client.post(
            "/api/charts/save",
            json={"title": "T", "query_config": {"exploreName": "o", "dimensions": ["a", "b"], "metrics": ["m"]}},
        )

        assert response.status_code == 422

    @mock.patch.object(routes.content, "create_chart")
    def test_reports_the_server_message_when_the_save_is_rejected(
        self, create_chart: mock.AsyncMock, client: testclient.TestClient
    ) -> None:
        create_chart.side_effect = content.SaveRejected(server_message="no permission")

        response = client.post(
            "/api/charts/save",
            json={"title": "T", "query_config": {"exploreName": "o", "dimensions": ["a"], "metrics": ["m"]}},
        )

        assert (response.status_code, response.json()["detail"]) == (422, "no permission")


class TestFiltersReachSaveAndExplore:
    @mock.patch.object(routes.content, "create_chart")
    def test_save_writes_the_filters_into_the_chart(
        self, create_chart: mock.AsyncMock, client: testclient.TestClient
    ) -> None:
        create_chart.return_value = content.SavedChart(href="/x", uuid="u")
        filters = {"dimensions": {"id": "g", "and": [{"id": "r"}]}}

        client.post(
            "/api/charts/save",
            json={
                "title": "T",
                "query_config": {"exploreName": "o", "dimensions": ["a"], "metrics": ["m"]},
                "lightdash_filters": filters,
            },
        )

        assert create_chart.call_args.kwargs["content"]["metricQuery"]["filters"] == filters

    def test_explore_link_carries_the_filters(self, client: testclient.TestClient) -> None:
        filters = {"dimensions": {"id": "g", "and": [{"id": "r"}]}}

        response = client.post(
            "/api/explore-url",
            json={"query_config": {"exploreName": "o", "dimensions": ["a"], "metrics": ["m"]}, "lightdash_filters": filters},
        )

        assert "inThePast" not in response.json()["url"]  # sanity: operator is inside the encoded blob
        assert "%22and%22" in response.json()["url"]
