from unittest import mock

import pytest
from mcp import types

from lightdash_companion_integration_spike.lightdash import mcp_app, queries


class FakeClient:
    def __init__(self, *, resource: list[object], tool_result: types.CallToolResult | None = None) -> None:
        self.resource = resource
        self.tool_result = tool_result
        self.read_uris: list[str] = []
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def read_resource(self, uri: str) -> list[object]:
        self.read_uris.append(uri)
        return self.resource

    async def call_tool_mcp(self, name: str, arguments: dict[str, object]) -> types.CallToolResult:
        self.calls.append((name, arguments))
        assert self.tool_result is not None
        return self.tool_result


def html_resource(text: str) -> types.TextResourceContents:
    return types.TextResourceContents(uri="ui://render-chart/chart.html", text=text, mimeType="text/html;profile=mcp-app")


class TestReadHtml:
    @pytest.mark.asyncio
    async def test_returns_the_text_of_the_apps_ui_resource(self) -> None:
        client = FakeClient(resource=[html_resource("<html></html>")])

        html = await mcp_app.read_html(client=client)  # type: ignore[arg-type]  # fake client

        assert html == "<html></html>"
        assert client.read_uris == [mcp_app.UI_RESOURCE_URI]

    @pytest.mark.asyncio
    async def test_raises_when_the_resource_has_no_html(self) -> None:
        client = FakeClient(resource=[html_resource("")])

        with pytest.raises(mcp_app.MissingAppHtml):
            await mcp_app.read_html(client=client)  # type: ignore[arg-type]  # fake client


class TestRenderChart:
    @pytest.mark.asyncio
    async def test_returns_the_whole_result_including_meta_rows(self) -> None:
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text="ok")],
            structuredContent={"result": {"status": "done"}},
            _meta={"result": {"rows": [{"a": 1}]}},
        )
        client = FakeClient(resource=[], tool_result=result)

        rendered = await mcp_app.render_chart(
            client=client,  # type: ignore[arg-type]  # fake client
            scope=queries.scope(project_uuid="p", agent_uuid=None),
            query_uuid="q",
            title="t",
            description="d",
            chart_config={"defaultVizType": "bar"},
        )

        assert rendered["_meta"] == {"result": {"rows": [{"a": 1}]}}
        assert rendered["structuredContent"] == {"result": {"status": "done"}}

    @pytest.mark.asyncio
    async def test_sends_scope_query_and_a_complete_chart_config(self) -> None:
        client = FakeClient(
            resource=[], tool_result=types.CallToolResult(content=[types.TextContent(type="text", text="ok")])
        )

        await mcp_app.render_chart(
            client=client,  # type: ignore[arg-type]  # fake client
            scope=queries.scope(project_uuid="p", agent_uuid="a"),
            query_uuid="q",
            title="t",
            description="d",
            chart_config={"defaultVizType": "bar"},
        )

        [(name, arguments)] = client.calls
        assert name == "render_chart"
        assert arguments == {
            "projectUuid": "p",
            "agentUuid": "a",
            "queryUuid": "q",
            "title": "t",
            "description": "d",
            "chartConfig": {"defaultVizType": "bar", "xAxisLabel": "", "yAxisLabel": ""},
        }

    @pytest.mark.asyncio
    async def test_omits_chart_config_when_there_is_none(self) -> None:
        client = FakeClient(
            resource=[], tool_result=types.CallToolResult(content=[types.TextContent(type="text", text="ok")])
        )

        await mcp_app.render_chart(
            client=client,  # type: ignore[arg-type]  # fake client
            scope={"projectUuid": "p"},
            query_uuid="q",
            title="t",
            description="",
            chart_config=None,
        )

        assert "chartConfig" not in client.calls[0][1]
