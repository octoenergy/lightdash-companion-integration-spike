from lightdash_companion_integration_spike import config


class TestSettings:
    def test_treats_blank_optional_values_as_unset(self) -> None:
        settings = config.Settings(
            lightdash_url="https://ld.example.com",
            lightdash_token="t",
            project_uuid="p",
            agent_uuid="",
            embed_secret="",
        )

        assert (settings.agent_uuid, settings.embed_secret) == (None, None)

    def test_keeps_real_optional_values(self) -> None:
        settings = config.Settings(
            lightdash_url="https://ld.example.com",
            lightdash_token="t",
            project_uuid="p",
            agent_uuid="11111111-1111-4111-8111-111111111111",
        )

        assert settings.agent_uuid == "11111111-1111-4111-8111-111111111111"
