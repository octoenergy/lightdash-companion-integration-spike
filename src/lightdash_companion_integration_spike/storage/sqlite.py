import json
import sqlite3
import uuid
from collections.abc import Mapping

import attrs

from lightdash_companion_integration_spike.domain import artifacts, blocks

SCHEMA = """
CREATE TABLE IF NOT EXISTS thread (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES thread(id),
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    blocks_json TEXT NOT NULL,
    seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_version (
    thread_id TEXT NOT NULL REFERENCES thread(id),
    artifact_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    query_args_json TEXT NOT NULL,
    message_id TEXT NOT NULL REFERENCES message(id),
    PRIMARY KEY (thread_id, artifact_id, version)
);
CREATE TABLE IF NOT EXISTS feedback (
    message_id TEXT PRIMARY KEY REFERENCES message(id),
    rating TEXT NOT NULL
);
"""

USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"


@attrs.frozen
class StoredMessage:
    id: str
    role: str
    text: str
    blocks: list[blocks.Block]


def connect(*, path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def create_thread(*, connection: sqlite3.Connection, title: str) -> str:
    thread_id = str(uuid.uuid4())
    connection.execute("INSERT INTO thread (id, title) VALUES (?, ?)", (thread_id, title))
    connection.commit()
    return thread_id


DEFAULT_THREAD_TITLE = "New chat"
TITLE_LENGTH = 60


def title_thread_if_untitled(*, connection: sqlite3.Connection, thread_id: str, question: str) -> None:
    """
    Name a thread after its first question so the sidebar can tell conversations apart.
    """
    connection.execute(
        "UPDATE thread SET title = ? WHERE id = ? AND title = ?",
        (question.strip()[:TITLE_LENGTH], thread_id, DEFAULT_THREAD_TITLE),
    )
    connection.commit()


def list_threads(*, connection: sqlite3.Connection) -> list[dict[str, str]]:
    rows = connection.execute("SELECT id, title FROM thread ORDER BY rowid DESC").fetchall()
    return [{"id": row["id"], "title": row["title"]} for row in rows]


def add_message(
    *,
    connection: sqlite3.Connection,
    thread_id: str,
    role: str,
    text: str,
    message_blocks: list[blocks.Block],
) -> str:
    message_id = str(uuid.uuid4())
    next_seq = connection.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 FROM message WHERE thread_id = ?", (thread_id,)
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO message (id, thread_id, role, text, blocks_json, seq) VALUES (?, ?, ?, ?, ?, ?)",
        (
            message_id,
            thread_id,
            role,
            text,
            json.dumps(blocks.BlockList.dump_python(message_blocks)),
            next_seq,
        ),
    )
    connection.commit()
    return message_id


def list_messages(*, connection: sqlite3.Connection, thread_id: str) -> list[StoredMessage]:
    rows = connection.execute(
        "SELECT id, role, text, blocks_json FROM message WHERE thread_id = ? ORDER BY seq",
        (thread_id,),
    ).fetchall()
    return [
        StoredMessage(
            id=row["id"],
            role=row["role"],
            text=row["text"],
            blocks=blocks.BlockList.validate_python(json.loads(row["blocks_json"])),
        )
        for row in rows
    ]


def save_artifact_version(
    *,
    connection: sqlite3.Connection,
    thread_id: str,
    artifact_id: str,
    title: str,
    query_args: Mapping[str, object],
    message_id: str,
) -> int:
    version = artifacts.next_version(
        existing=list_artifact_versions(connection=connection, thread_id=thread_id),
        artifact_id=artifact_id,
    )
    connection.execute(
        "INSERT INTO artifact_version "
        "(thread_id, artifact_id, version, title, query_args_json, message_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (thread_id, artifact_id, version, title, json.dumps(query_args), message_id),
    )
    connection.commit()
    return version


def list_artifact_versions(
    *, connection: sqlite3.Connection, thread_id: str
) -> list[artifacts.ArtifactVersion]:
    rows = connection.execute(
        "SELECT artifact_id, version, title, query_args_json FROM artifact_version "
        "WHERE thread_id = ? ORDER BY artifact_id, version",
        (thread_id,),
    ).fetchall()
    return [
        artifacts.ArtifactVersion(
            artifact_id=row["artifact_id"],
            version=row["version"],
            title=row["title"],
            query_args=json.loads(row["query_args_json"]),
        )
        for row in rows
    ]


def save_feedback(*, connection: sqlite3.Connection, message_id: str, rating: str) -> None:
    connection.execute(
        "INSERT INTO feedback (message_id, rating) VALUES (?, ?) "
        "ON CONFLICT(message_id) DO UPDATE SET rating = excluded.rating",
        (message_id, rating),
    )
    connection.commit()


def get_feedback(*, connection: sqlite3.Connection, message_id: str) -> str | None:
    row = connection.execute(
        "SELECT rating FROM feedback WHERE message_id = ?", (message_id,)
    ).fetchone()
    return row["rating"] if row else None
