import pydantic_ai
from pydantic_ai import messages

from lightdash_companion_integration_spike.domain import artifacts
from lightdash_companion_integration_spike.storage import sqlite

USER_ROLE = sqlite.USER_ROLE


def build_message_history(
    *,
    stored: list[sqlite.StoredMessage],
    existing_artifacts: list[artifacts.ArtifactVersion],
) -> list[messages.ModelMessage]:
    """
    Replay earlier turns as text, then describe the latest version of each chart.

    Lightdash keeps no state between calls, so without this the model cannot edit an earlier
    query on a follow-up like "now split that by month".
    """
    history: list[messages.ModelMessage] = []
    for message in stored:
        if message.role == USER_ROLE:
            history.append(messages.ModelRequest(parts=[messages.UserPromptPart(content=message.text)]))
        else:
            history.append(messages.ModelResponse(parts=[messages.TextPart(content=message.text)]))

    if existing_artifacts:
        context = (
            "Charts already shown in this conversation (reuse the artifact_id to edit one):\n"
            + artifacts.summarize_for_llm(existing=existing_artifacts)
        )
        history.insert(0, messages.ModelRequest(parts=[messages.SystemPromptPart(content=context)]))
    return history
