from collections.abc import Iterable, Mapping

import attrs

NEW_ARTIFACT = "new"


@attrs.frozen
class ArtifactVersion:
    artifact_id: str
    version: int
    title: str
    query_args: Mapping[str, object]


def next_version(*, existing: Iterable[ArtifactVersion], artifact_id: str) -> int:
    """
    Return the version number a new save of the artifact should receive.
    """
    versions = [item.version for item in existing if item.artifact_id == artifact_id]
    return max(versions, default=0) + 1


def latest_versions(*, existing: Iterable[ArtifactVersion]) -> list[ArtifactVersion]:
    """
    Return the newest version of each artifact, ordered by artifact id.
    """
    latest: dict[str, ArtifactVersion] = {}
    for item in existing:
        current = latest.get(item.artifact_id)
        if current is None or item.version > current.version:
            latest[item.artifact_id] = item
    return [latest[artifact_id] for artifact_id in sorted(latest)]


def summarize_for_llm(*, existing: Iterable[ArtifactVersion]) -> str:
    """
    Describe the latest version of each artifact so the model can edit it on a follow-up.
    """
    lines = [
        f"- artifact_id={item.artifact_id} v{item.version} '{item.title}' query_args={dict(item.query_args)}"
        for item in latest_versions(existing=existing)
    ]
    return "\n".join(lines)
