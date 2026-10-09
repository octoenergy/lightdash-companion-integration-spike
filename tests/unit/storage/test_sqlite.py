import sqlite3

import pytest

from lightdash_companion_integration_spike.domain import blocks
from lightdash_companion_integration_spike.storage import sqlite


@pytest.fixture
def connection() -> sqlite3.Connection:
    return sqlite.connect(path=":memory:")


def _add(connection: sqlite3.Connection, thread_id: str, role: str, text: str) -> str:
    return sqlite.add_message(
        connection=connection,
        thread_id=thread_id,
        role=role,
        text=text,
        message_blocks=[blocks.MarkdownBlock(text=text)],
    )


class TestMessages:
    def test_lists_messages_in_the_order_they_were_added(self, connection: sqlite3.Connection) -> None:
        thread_id = sqlite.create_thread(connection=connection, title="t")
        _add(connection, thread_id, sqlite.USER_ROLE, "first")
        _add(connection, thread_id, sqlite.ASSISTANT_ROLE, "second")

        messages = sqlite.list_messages(connection=connection, thread_id=thread_id)

        assert [(message.role, message.text) for message in messages] == [
            ("user", "first"),
            ("assistant", "second"),
        ]

    def test_restores_blocks_as_typed_objects(self, connection: sqlite3.Connection) -> None:
        thread_id = sqlite.create_thread(connection=connection, title="t")
        _add(connection, thread_id, sqlite.ASSISTANT_ROLE, "hello")

        messages = sqlite.list_messages(connection=connection, thread_id=thread_id)

        assert messages[0].blocks == [blocks.MarkdownBlock(text="hello")]


class TestTitleThreadIfUntitled:
    def test_names_a_new_thread_after_its_first_question(self, connection: sqlite3.Connection) -> None:
        thread_id = sqlite.create_thread(connection=connection, title=sqlite.DEFAULT_THREAD_TITLE)

        sqlite.title_thread_if_untitled(connection=connection, thread_id=thread_id, question="Active supply points?")

        assert sqlite.list_threads(connection=connection)[0]["title"] == "Active supply points?"

    def test_keeps_the_title_once_a_thread_has_one(self, connection: sqlite3.Connection) -> None:
        thread_id = sqlite.create_thread(connection=connection, title=sqlite.DEFAULT_THREAD_TITLE)
        sqlite.title_thread_if_untitled(connection=connection, thread_id=thread_id, question="First")

        sqlite.title_thread_if_untitled(connection=connection, thread_id=thread_id, question="Second")

        assert sqlite.list_threads(connection=connection)[0]["title"] == "First"


class TestThreads:
    def test_lists_newest_thread_first(self, connection: sqlite3.Connection) -> None:
        sqlite.create_thread(connection=connection, title="older")
        sqlite.create_thread(connection=connection, title="newer")

        titles = [thread["title"] for thread in sqlite.list_threads(connection=connection)]

        assert titles == ["newer", "older"]


class TestArtifactVersions:
    def test_a_second_save_of_the_same_artifact_becomes_version_two(
        self, connection: sqlite3.Connection
    ) -> None:
        thread_id = sqlite.create_thread(connection=connection, title="t")
        message_id = _add(connection, thread_id, sqlite.ASSISTANT_ROLE, "x")

        versions = [
            sqlite.save_artifact_version(
                connection=connection,
                thread_id=thread_id,
                artifact_id="a",
                title="Chart",
                query_args={"n": number},
                message_id=message_id,
            )
            for number in (1, 2)
        ]

        assert versions == [1, 2]

    def test_keeps_query_args_for_each_version(self, connection: sqlite3.Connection) -> None:
        thread_id = sqlite.create_thread(connection=connection, title="t")
        message_id = _add(connection, thread_id, sqlite.ASSISTANT_ROLE, "x")
        for number in (1, 2):
            sqlite.save_artifact_version(
                connection=connection,
                thread_id=thread_id,
                artifact_id="a",
                title="Chart",
                query_args={"n": number},
                message_id=message_id,
            )

        stored = sqlite.list_artifact_versions(connection=connection, thread_id=thread_id)

        assert [(item.version, dict(item.query_args)) for item in stored] == [
            (1, {"n": 1}),
            (2, {"n": 2}),
        ]


class TestFeedback:
    def test_a_later_rating_replaces_the_earlier_one(self, connection: sqlite3.Connection) -> None:
        thread_id = sqlite.create_thread(connection=connection, title="t")
        message_id = _add(connection, thread_id, sqlite.ASSISTANT_ROLE, "x")

        sqlite.save_feedback(connection=connection, message_id=message_id, rating="up")
        sqlite.save_feedback(connection=connection, message_id=message_id, rating="down")

        assert sqlite.get_feedback(connection=connection, message_id=message_id) == "down"

    def test_returns_nothing_when_unrated(self, connection: sqlite3.Connection) -> None:
        assert sqlite.get_feedback(connection=connection, message_id="missing") is None
