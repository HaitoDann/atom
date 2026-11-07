"""Canevas (comme Canvas / Artifacts) : un document ou un code ouvert à côté de la conversation,
modifié à deux — par toi directement, ou par Atom sur consigne (sur tout le texte ou une sélection),
avec un historique des versions."""

from __future__ import annotations

import json
import re
import time

from . import db, hybrid, llm
from .config import DEFAULT_MODEL
import logging

log = logging.getLogger("atom.canvas")

MAX_VERSIONS = 30


def init() -> None:
    with db.conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS canvases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER, title TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'doc', content TEXT NOT NULL DEFAULT '', versions TEXT NOT NULL DEFAULT '[]',
            created_at REAL NOT NULL, updated_at REAL NOT NULL)""")


def _row(r) -> dict:
    d = dict(r)
    v = json.loads(d.pop("versions") or "[]")
    d["versions"] = [{"i": i, "at": x["at"], "by": x["by"], "note": x.get("note", "")} for i, x in enumerate(v)]
    return d


def get(cid: int) -> dict | None:
    with db.conn() as c:
        r = c.execute("SELECT * FROM canvases WHERE id = ?", (cid,)).fetchone()
    return _row(r) if r else None


def list_for(conversation_id: int | None) -> list[dict]:
    with db.conn() as c:
        if conversation_id:
            rows = c.execute("SELECT id, title, kind, conversation_id, updated_at FROM canvases WHERE conversation_id = ? ORDER BY updated_at DESC", (conversation_id,)).fetchall()
        else:
            rows = c.execute("SELECT id, title, kind, conversation_id, updated_at FROM canvases ORDER BY updated_at DESC LIMIT 50").fetchall()
    return [dict(r) for r in rows]


def create(title: str, content: str, conversation_id: int | None, kind: str = "doc") -> int:
    now = time.time()
    v = [{"at": now, "by": "création", "content": content}]
    with db.conn() as c:
        return c.execute("INSERT INTO canvases (conversation_id, title, kind, content, versions, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (conversation_id, title.strip()[:120] or "Sans titre", kind, content, json.dumps(v), now, now)).lastrowid


def save(cid: int, content: str, by: str = "toi", note: str = "", title: str | None = None) -> dict:
    with db.conn() as c:
        r = c.execute("SELECT versions, content FROM canvases WHERE id = ?", (cid,)).fetchone()
        if not r:
            raise KeyError("canevas")
        v = json.loads(r["versions"] or "[]")
        if content != r["content"]:
            v.append({"at": time.time(), "by": by, "note": note[:200], "content": content})
            v = v[-MAX_VERSIONS:]
        sets, args = ["content = ?", "versions = ?", "updated_at = ?"], [content, json.dumps(v), time.time()]
        if title is not None:
            sets.append("title = ?"); args.append(title.strip()[:120] or "Sans titre")
        c.execute(f"UPDATE canvases SET {', '.join(sets)} WHERE id = ?", (*args, cid))
    return get(cid)


def version(cid: int, i: int) -> str:
    with db.conn() as c:
        r = c.execute("SELECT versions FROM canvases WHERE id = ?", (cid,)).fetchone()
    v = json.loads(r["versions"]) if r else []
    if not 0 <= i < len(v):
        raise KeyError("version")
    return v[i]["content"]


def delete(cid: int) -> None:
    with db.conn() as c:
        c.execute("DELETE FROM canvases WHERE id = ?", (cid,))


async def edit(cid: int, instruction: str, selection: str = "", engine: str = "auto") -> dict:
    cv = get(cid)
    if not cv:
        raise KeyError("canevas")
    doc = cv["content"]
    code = cv["kind"] == "code"
    target = selection if selection and selection in doc else doc
    partial = target is not doc and target != doc
    sys = ("Tu es le co-auteur d'un " + ("code source" if code else "document") + " ouvert dans un canevas. "
           "Applique la consigne et renvoie UNIQUEMENT le texte réécrit, sans commentaire, sans balise d'émotion, "
           "sans bloc de code englobant. Garde la langue, le ton et la mise en forme Markdown sauf demande contraire. /no_think")
    user = (f"Document complet (contexte) :\n<<<\n{doc[:12000]}\n>>>\n\nPassage à réécrire :\n<<<\n{target}\n>>>\n\nConsigne : {instruction}"
            if partial else f"Document :\n<<<\n{doc[:16000]}\n>>>\n\nConsigne : {instruction}")
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": user}]
    out = ""
    s = hybrid.settings()
    if engine != "local" and hybrid.configured() and s.get("allow_docs"):
        try:
            out = "".join([t async for t in hybrid.stream(msgs, sensitive=True)])
        except Exception:
            log.warning("canvas : erreur gérée", exc_info=True)
            out = ""
    if not out:
        out = "".join([t async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, msgs)])
    out = re.sub(r"^\s*\[[a-z_]+\]\s*", "", out).strip()
    m = re.fullmatch(r"```[\w-]*\n([\s\S]*?)\n?```", out)
    if m:
        out = m.group(1)
    out = out.strip("<>").strip() if out.startswith("<<<") else out
    if not out:
        raise RuntimeError("Atom n'a rien renvoyé.")
    new = doc.replace(target, out, 1) if partial else out
    return save(cid, new, by="Atom", note=instruction)
