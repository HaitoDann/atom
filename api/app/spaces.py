"""Espaces (comme les « Projets » de ChatGPT / Claude) : des conversations, des consignes et des documents
regroupés par sujet. Dans un espace, Atom suit ses consignes et cherche d'abord dans ses collections."""

from __future__ import annotations

import json
import time

from . import db


def init() -> None:
    with db.conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS spaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, instructions TEXT NOT NULL DEFAULT '',
            collections TEXT NOT NULL DEFAULT '[]', icon TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(conversations)")}
        if "space_id" not in cols:
            c.execute("ALTER TABLE conversations ADD COLUMN space_id INTEGER")


def _row(r) -> dict:
    d = dict(r)
    d["collections"] = json.loads(d.get("collections") or "[]")
    return d


def list_all() -> list[dict]:
    with db.conn() as c:
        rows = c.execute("SELECT s.*, (SELECT COUNT(*) FROM conversations WHERE space_id = s.id) AS conversations "
                         "FROM spaces s ORDER BY s.updated_at DESC").fetchall()
    return [_row(r) for r in rows]


def get(sid: int | None) -> dict | None:
    if not sid:
        return None
    with db.conn() as c:
        r = c.execute("SELECT * FROM spaces WHERE id = ?", (sid,)).fetchone()
    return _row(r) if r else None


def create(name: str, instructions: str = "", collections: list[int] | None = None) -> int:
    now = time.time()
    with db.conn() as c:
        return c.execute("INSERT INTO spaces (name, instructions, collections, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                         (name.strip()[:80], instructions.strip()[:8000], json.dumps(collections or []), now, now)).lastrowid


def update(sid: int, **f) -> None:
    if "collections" in f:
        f["collections"] = json.dumps([int(x) for x in f["collections"]])
    f["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in f)
    with db.conn() as c:
        c.execute(f"UPDATE spaces SET {cols} WHERE id = ?", (*f.values(), sid))


def delete(sid: int) -> None:
    """Supprime l'espace ; ses conversations restent (elles redeviennent libres)."""
    with db.conn() as c:
        c.execute("UPDATE conversations SET space_id = NULL WHERE space_id = ?", (sid,))
        c.execute("DELETE FROM spaces WHERE id = ?", (sid,))


def of_conversation(cid: int | None) -> dict | None:
    if not cid:
        return None
    with db.conn() as c:
        r = c.execute("SELECT space_id FROM conversations WHERE id = ?", (cid,)).fetchone()
    return get(r["space_id"]) if r and r["space_id"] else None


def assign(cid: int, sid: int | None) -> None:
    with db.conn() as c:
        c.execute("UPDATE conversations SET space_id = ? WHERE id = ?", (sid, cid))
    if sid:
        update(sid)


def prompt_block(space: dict) -> str:
    s = f"Cette conversation fait partie de l'espace « {space['name']} »."
    if space.get("instructions"):
        s += f" Consignes de cet espace (à suivre en priorité) :\n{space['instructions']}"
    return s
