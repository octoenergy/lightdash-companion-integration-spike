from lightdash_companion_integration_spike import config
from lightdash_companion_integration_spike.lightdash import mcp_client


class TestMcpUrl:
    def test_pins_session_to_project_and_strips_trailing_slash(self) -> None:
        settings = config.Settings(
            lightdash_url="https://ld.example.com/", lightdash_token="t", project_uuid="abc"
        )

        assert (
            mcp_client.mcp_url(settings=settings)
            == "https://ld.example.com/api/v1/mcp/projects/abc"
        )


class TestBuildHeaders:
    def test_omits_user_attributes_by_default(self) -> None:
        assert mcp_client.build_headers(token="t") == {"Authorization": "Bearer t"}

    def test_adds_user_attributes_header_when_given(self) -> None:
        headers = mcp_client.build_headers(token="t", attributes={"tenant_id": "1"})

        assert headers["X-Lightdash-User-Attributes"] == '{"tenant_id": "1"}'
