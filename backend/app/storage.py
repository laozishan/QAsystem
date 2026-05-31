import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from .config import settings


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            );
            """
        )


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def create_document(title: str, source: str) -> dict[str, Any]:
    document = {"id": str(uuid.uuid4()), "title": title, "source": source, "created_at": now_iso()}
    with connect() as conn:
        conn.execute(
            "INSERT INTO documents (id, title, source, created_at) VALUES (?, ?, ?, ?)",
            (document["id"], document["title"], document["source"], document["created_at"]),
        )
    return document


def list_documents() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    return [row_to_dict(row) for row in rows]


def delete_document(document_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


def create_conversation(title: str) -> dict[str, Any]:
    conversation = {"id": str(uuid.uuid4()), "title": title[:80] or "New chat", "created_at": now_iso()}
    with connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)",
            (conversation["id"], conversation["title"], conversation["created_at"]),
        )
    return conversation


def list_conversations() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM conversations ORDER BY created_at DESC").fetchall()
    return [row_to_dict(row) for row in rows]


def add_message(conversation_id: str, role: str, content: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), conversation_id, role, content, now_iso()),
        )


def get_messages(conversation_id: str, limit: int = 12) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()
    return [row_to_dict(row) for row in reversed(rows)]

