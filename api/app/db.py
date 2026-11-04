"""Stockage SQLite : conversations, messages, souvenirs.

Les embeddings sont stockés en BLOB float32 et comparés en mémoire (numpy).
À l'échelle d'une personne (quelques milliers de lignes), c'est instantané.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing, contextmanager

import numpy as np

from .config import DB_PATH


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    with closing(c):
        with c:
            yield c


def _columns(c, table: str) -> set[str]:
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}


def init() -> None:
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'Nouvelle conversation',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                emotion TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                text TEXT NOT NULL,
                due_at REAL NOT NULL,          -- timestamp UTC
                status TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | failed
                created_at REAL NOT NULL,
                sent_at REAL
            );
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            -- Échanges passés indexés pour le rappel sémantique
            CREATE TABLE IF NOT EXISTS recall (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        # Migrations depuis la v1 (historique unique, souvenirs manuels)
        if "conversation_id" not in _columns(c, "messages"):
            c.execute("ALTER TABLE messages ADD COLUMN conversation_id INTEGER")
            if c.execute("SELECT 1 FROM messages LIMIT 1").fetchone():
                now = time.time()
                cid = c.execute(
                    "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
                    ("Première conversation", now, now),
                ).lastrowid
                c.execute("UPDATE messages SET conversation_id = ?", (cid,))
        mem_cols = _columns(c, "memories")
        for col, ddl in [
            ("source", "TEXT NOT NULL DEFAULT 'manuel'"),
            ("embedding", "BLOB"),
            ("updated_at", "REAL"),
        ]:
            if col not in mem_cols:
                c.execute(f"ALTER TABLE memories ADD COLUMN {col} {ddl}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, id)")


# ---------------------------------------------------------------- conversations


def create_conversation(title: str = "Nouvelle conversation") -> int:
    now = time.time()
    with conn() as c:
        return c.execute(
            "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, now, now),
        ).lastrowid


def list_conversations() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def conversation_exists(cid: int) -> bool:
    with conn() as c:
        return c.execute("SELECT 1 FROM conversations WHERE id = ?", (cid,)).fetchone() is not None


def rename_conversation(cid: int, title: str) -> None:
    with conn() as c:
        c.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, cid))


def delete_conversation(cid: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
        c.execute("DELETE FROM recall WHERE conversation_id = ?", (cid,))
        c.execute("DELETE FROM conversations WHERE id = ?", (cid,))


# ---------------------------------------------------------------- messages


def add_message(cid: int, role: str, content: str, emotion: str | None = None) -> None:
    now = time.time()
    with conn() as c:
        c.execute(
            "INSERT INTO messages (conversation_id, role, content, emotion, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cid, role, content, emotion, now),
        )
        c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, cid))


def messages(cid: int, limit: int) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT role, content, emotion FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (cid, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ---------------------------------------------------------------- souvenirs


def to_blob(v: np.ndarray | None) -> bytes | None:
    return None if v is None else np.asarray(v, dtype=np.float32).tobytes()


def from_blob(b: bytes | None) -> np.ndarray | None:
    return None if b is None else np.frombuffer(b, dtype=np.float32)


def list_memories() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id, content, source, created_at, updated_at, embedding FROM memories ORDER BY id"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["embedding"] = from_blob(d["embedding"])
        out.append(d)
    return out


def add_memory(content: str, source: str, embedding: np.ndarray | None) -> int:
    now = time.time()
    with conn() as c:
        return c.execute(
            "INSERT INTO memories (content, source, embedding, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (content, source, to_blob(embedding), now, now),
        ).lastrowid


def update_memory(mid: int, content: str, embedding: np.ndarray | None) -> bool:
    with conn() as c:
        return c.execute(
            "UPDATE memories SET content = ?, embedding = ?, updated_at = ? WHERE id = ?",
            (content, to_blob(embedding), time.time(), mid),
        ).rowcount > 0


def set_memory_embedding(mid: int, embedding: np.ndarray) -> None:
    with conn() as c:
        c.execute("UPDATE memories SET embedding = ? WHERE id = ?", (to_blob(embedding), mid))


def delete_memory(mid: int) -> bool:
    with conn() as c:
        return c.execute("DELETE FROM memories WHERE id = ?", (mid,)).rowcount > 0


def clear_memories() -> None:
    with conn() as c:
        c.execute("DELETE FROM memories")


# ---------------------------------------------------------------- rappel


def add_recall(cid: int, text: str, embedding: np.ndarray) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO recall (conversation_id, text, embedding, created_at) VALUES (?, ?, ?, ?)",
            (cid, text, to_blob(embedding), time.time()),
        )


def list_recall() -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT conversation_id, text, embedding, created_at FROM recall").fetchall()
    return [{**dict(r), "embedding": from_blob(r["embedding"])} for r in rows]


# ---------------------------------------------------------------- rappels (tâches)


def add_reminder(cid: int | None, text: str, due_at: float) -> int:
    with conn() as c:
        return c.execute(
            "INSERT INTO reminders (conversation_id, text, due_at, created_at) VALUES (?, ?, ?, ?)",
            (cid, text, due_at, time.time()),
        ).lastrowid


def list_reminders(status: str | None = "pending", limit: int = 200) -> list[dict]:
    with conn() as c:
        if status:
            rows = c.execute(
                "SELECT * FROM reminders WHERE status = ? ORDER BY due_at LIMIT ?", (status, limit)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM reminders ORDER BY due_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def due_reminders(now: float) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM reminders WHERE status = 'pending' AND due_at <= ? ORDER BY due_at", (now,)
        ).fetchall()
    return [dict(r) for r in rows]


def mark_reminder(rid: int, status: str) -> None:
    with conn() as c:
        c.execute(
            "UPDATE reminders SET status = ?, sent_at = ? WHERE id = ?", (status, time.time(), rid)
        )


def delete_reminder(rid: int) -> bool:
    with conn() as c:
        return c.execute(
            "DELETE FROM reminders WHERE id = ? AND status = 'pending'", (rid,)
        ).rowcount > 0


# ---------------------------------------------------------------- clé / valeur


def kv_get(key: str, default: str | None = None) -> str | None:
    with conn() as c:
        r = c.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else default


def kv_set(key: str, value: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
