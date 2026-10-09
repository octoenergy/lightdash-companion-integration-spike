from lightdash_companion_integration_spike.agent import agent


class TestComposeInstructions:
    def test_uses_only_our_rules_when_the_server_gave_no_guidance(self) -> None:
        assert agent.compose_instructions(server_guidance=None) == agent.INSTRUCTIONS

    def test_appends_the_servers_guidance_after_our_rules(self) -> None:
        composed = agent.compose_instructions(server_guidance="USE get_metadata")

        assert composed.startswith(agent.INSTRUCTIONS)
        assert composed.endswith("USE get_metadata")
