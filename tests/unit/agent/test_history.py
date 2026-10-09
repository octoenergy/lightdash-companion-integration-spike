from pydantic_ai import messages

from lightdash_companion_integration_spike.agent import history
from lightdash_companion_integration_spike.domain import artifacts, blocks
from lightdash_companion_integration_spike.storage import sqlite


def _stored(role: str, text: str) -> sqlite.StoredMessage:
    return sqlite.StoredMessage(id="m", role=role, text=text, blocks=[blocks.MarkdownBlock(text=text)])


class TestBuildMessageHistory:
    def test_replays_user_and_assistant_turns_in_order(self) -> None:
        built = history.build_message_history(
            stored=[_stored("user", "q1"), _stored("assistant", "a1")], existing_artifacts=[]
        )

        assert [type(message).__name__ for message in built] == ["ModelRequest", "ModelResponse"]

    def test_leads_with_the_latest_chart_queries_so_the_model_can_edit_them(self) -> None:
        chart = artifacts.ArtifactVersion(
            artifact_id="abc", version=2, title="Revenue", query_args={"queryConfig": {"exploreName": "orders"}}
        )

        built = history.build_message_history(stored=[_stored("user", "q1")], existing_artifacts=[chart])

        first_part = built[0].parts[0]
        assert isinstance(first_part, messages.SystemPromptPart)
        assert "artifact_id=abc v2 'Revenue'" in first_part.content
