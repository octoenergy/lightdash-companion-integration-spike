from lightdash_companion_integration_spike.domain import artifacts


def _version(artifact_id: str, version: int) -> artifacts.ArtifactVersion:
    return artifacts.ArtifactVersion(
        artifact_id=artifact_id, version=version, title="t", query_args={"v": version}
    )


class TestNextVersion:
    def test_starts_at_one_for_unseen_artifact(self) -> None:
        assert artifacts.next_version(existing=[_version("a", 1)], artifact_id="b") == 1

    def test_increments_past_the_highest_version(self) -> None:
        existing = [_version("a", 1), _version("a", 3)]

        assert artifacts.next_version(existing=existing, artifact_id="a") == 4


class TestLatestVersions:
    def test_keeps_only_newest_version_per_artifact(self) -> None:
        existing = [_version("a", 1), _version("a", 2), _version("b", 1)]

        latest = artifacts.latest_versions(existing=existing)

        assert [(item.artifact_id, item.version) for item in latest] == [("a", 2), ("b", 1)]


class TestSummarizeForLlm:
    def test_includes_latest_query_args(self) -> None:
        summary = artifacts.summarize_for_llm(existing=[_version("a", 1), _version("a", 2)])

        assert summary == "- artifact_id=a v2 't' query_args={'v': 2}"
