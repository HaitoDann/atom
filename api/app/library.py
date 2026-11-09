"""Bibliothèque : tes documents et tes projets de code, découpés et indexés.

- Collections de documents (PDF, Word, texte, Markdown…) ajoutés depuis l'interface.
- Projets de code : un dépôt GitHub (cloné) ou un dossier du serveur (/projects), en lecture seule.
- Chaque fichier est découpé en passages, chaque passage reçoit un embedding (nomic-embed-text).
- À chaque message, les passages les plus proches sont donnés au modèle, avec leur source.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import shutil
import time
from pathlib import Path

import numpy as np

from . import db, llm
from .config import DATA_DIR
from .extract import Unsupported, chunk_code, chunk_text, extract_pages  # noqa: F401 (API publique)

log = logging.getLogger("atom.library")
FILES_DIR = DATA_DIR / "library"
REPOS_DIR = DATA_DIR / "repos"

DOC_MIN_SCORE = float(os.getenv("ATOM_DOC_MIN_SCORE", "0.5"))

CODE_EXT = {
    "py", "js", "mjs", "cjs", "ts", "tsx", "jsx", "vue", "svelte", "go", "rs", "java", "kt", "c", "h", "cpp",
    "hpp", "cc", "cs", "rb", "php", "lua", "sh", "bash", "zsh", "ps1", "sql", "html", "htm", "css", "scss",
    "sass", "less", "json", "yaml", "yml", "toml", "ini", "cfg", "conf", "env", "md", "markdown", "txt", "rst",
    "dockerfile", "makefile", "gradle", "tf", "hcl", "nix", "graphql", "proto", "xml", "swift", "dart", "ex",
    "exs", "erl", "hs", "scala", "r", "jl", "zig", "nim", "pl", "vim", "readme", "license", "gitignore",
}
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "target", ".next", ".nuxt", "__pycache__",
             ".venv", "venv", "env", ".idea", ".vscode", "coverage", ".cache", ".pytest_cache", ".mypy_cache",
             "bower_components", ".terraform", "out", "bin", "obj"}
SKIP_FILES = re.compile(r"(\.min\.(js|css)$|\.lock$|package-lock\.json$|yarn\.lock$|pnpm-lock\.yaml$|\.map$)", re.I)
MAX_CODE_FILE = 300_000
MAX_CODE_FILES = 3000
PROGRESS: dict[int, dict] = {}   # cid → {phase, done, total, started} (indexation des projets de code)
EMBED_BATCH = int(os.getenv("ATOM_EMBED_BATCH", "64"))


# ---------------------------------------------------------------- schéma


def init() -> None:
    with db.conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'docs',     -- docs | code
                source TEXT,                           -- URL GitHub ou chemin serveur (code)
                status TEXT NOT NULL DEFAULT 'ready',  -- ready | indexing | error
                message TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                path TEXT,                             -- fichier stocké, ou chemin dans le projet
                size INTEGER NOT NULL DEFAULT 0,
                pages INTEGER,
                chars INTEGER NOT NULL DEFAULT 0,
                hash TEXT,
                status TEXT NOT NULL DEFAULT 'ready',  -- ready | indexing | error
                message TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                collection_id INTEGER NOT NULL,
                ord INTEGER NOT NULL,
                page INTEGER,
                line_start INTEGER,
                line_end INTEGER,
                text TEXT NOT NULL,
                embedding BLOB
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_docs_coll ON documents(collection_id);
            """
        )
        if not c.execute("SELECT 1 FROM collections WHERE kind = 'docs' LIMIT 1").fetchone():
            now = time.time()
            c.execute("INSERT INTO collections (name, kind, created_at, updated_at) VALUES ('Mes documents', 'docs', ?, ?)",
                      (now, now))


# ---------------------------------------------------------------- extraction de texte (app/extract.py)


# ---------------------------------------------------------------- index en mémoire (recherche rapide)

_index: dict = {"version": -1}
_version = 0


def _bump() -> None:
    global _version
    _version += 1


def _load_index() -> dict:
    if _index.get("version") == _version:
        return _index
    with db.conn() as c:
        rows = c.execute("SELECT id, collection_id, embedding FROM chunks WHERE embedding IS NOT NULL").fetchall()
    ids = np.array([r["id"] for r in rows], dtype=np.int64)
    colls = np.array([r["collection_id"] for r in rows], dtype=np.int64)
    mat = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]) if rows else np.zeros((0, 1), np.float32)
    _index.update(version=_version, ids=ids, colls=colls, mat=mat)
    return _index


async def retrieve(query: str, collection_ids: list[int] | None, k: int = 5, min_score: float = DOC_MIN_SCORE) -> list[dict]:
    idx = _load_index()
    if not len(idx["ids"]):
        return []
    q = await llm.embed([query], kind="query")
    if not q or q[0].shape[0] != idx["mat"].shape[1]:
        return []
    scores = idx["mat"] @ q[0]
    if collection_ids is not None:
        scores = np.where(np.isin(idx["colls"], collection_ids), scores, -1)
    order = np.argsort(-scores)[: k * 3]
    picked = [(int(idx["ids"][i]), float(scores[i])) for i in order if scores[i] >= min_score][: k * 2]
    if not picked:
        return []
    with db.conn() as c:
        qmarks = ",".join("?" * len(picked))
        rows = {r["id"]: dict(r) for r in c.execute(
            f"SELECT ch.id, ch.document_id, ch.collection_id, ch.page, ch.line_start, ch.line_end, ch.text, "
            f"d.name, d.path, co.name AS collection, co.kind FROM chunks ch "
            f"JOIN documents d ON d.id = ch.document_id JOIN collections co ON co.id = ch.collection_id "
            f"WHERE ch.id IN ({qmarks})", [p[0] for p in picked])}
    out, per_doc = [], {}
    for cid, score in picked:
        r = rows.get(cid)
        if not r:
            continue
        if per_doc.get(r["document_id"], 0) >= 2:   # variété : 2 passages max par document
            continue
        per_doc[r["document_id"]] = per_doc.get(r["document_id"], 0) + 1
        r["score"] = round(score, 3)
        out.append(r)
        if len(out) >= k:
            break
    return out


def ref_label(r: dict) -> str:
    if r["kind"] == "code":
        return f"{r['path']} l.{r['line_start']}-{r['line_end']}"
    return f"{r['name']}" + (f", p. {r['page']}" if r.get("page") else "")


def prompt_block(results: list[dict]) -> str:
    from .security import UNTRUSTED_RULE, untrusted
    lines = [UNTRUSTED_RULE, "", "Extraits de la bibliothèque de l'utilisateur (documents et code) pertinents pour sa question :", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"[D{i}] {ref_label(r)} — collection « {r['collection']} »\n" + untrusted(r["text"], "document de la bibliothèque") + "\n")
    lines.append("Appuie-toi sur ces extraits quand ils sont utiles et cite-les par leur numéro, par exemple [D1]. "
                 "S'ils ne contiennent pas la réponse, dis-le plutôt que d'inventer.")
    return "\n".join(lines)


# ---------------------------------------------------------------- collections


def list_collections() -> list[dict]:
    with db.conn() as c:
        rows = c.execute(
            "SELECT co.*, (SELECT COUNT(*) FROM documents d WHERE d.collection_id = co.id) AS documents, "
            "(SELECT COUNT(*) FROM chunks ch WHERE ch.collection_id = co.id) AS chunks "
            "FROM collections co ORDER BY co.kind DESC, co.name").fetchall()
    out = [dict(r) for r in rows]
    for c in out:
        if c["id"] in PROGRESS:
            c["progress"] = {k: v for k, v in PROGRESS[c["id"]].items()}
    return out


def create_collection(name: str, kind: str = "docs", source: str | None = None) -> int:
    now = time.time()
    with db.conn() as c:
        return c.execute("INSERT INTO collections (name, kind, source, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (name, kind, source, "indexing" if kind == "code" else "ready", now, now)).lastrowid


def get_collection(cid: int) -> dict | None:
    with db.conn() as c:
        r = c.execute("SELECT * FROM collections WHERE id = ?", (cid,)).fetchone()
    return dict(r) if r else None


def set_collection(cid: int, **fields) -> None:
    fields["updated_at"] = time.time()
    with db.conn() as c:
        c.execute(f"UPDATE collections SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?", (*fields.values(), cid))


def rename_collection(cid: int, name: str) -> None:
    set_collection(cid, name=name)


def delete_collection(cid: int) -> None:
    col = get_collection(cid)
    with db.conn() as c:
        for r in c.execute("SELECT path FROM documents WHERE collection_id = ?", (cid,)).fetchall():
            if col and col["kind"] == "docs" and r["path"]:
                Path(r["path"]).unlink(missing_ok=True)
        c.execute("DELETE FROM chunks WHERE collection_id = ?", (cid,))
        c.execute("DELETE FROM documents WHERE collection_id = ?", (cid,))
        c.execute("DELETE FROM collections WHERE id = ?", (cid,))
    shutil.rmtree(REPOS_DIR / str(cid), ignore_errors=True)
    _bump()


def list_documents(cid: int) -> list[dict]:
    with db.conn() as c:
        rows = c.execute(
            "SELECT d.id, d.name, d.path, d.size, d.pages, d.chars, d.status, d.message, d.created_at, "
            "(SELECT COUNT(*) FROM chunks ch WHERE ch.document_id = d.id) AS chunks "
            "FROM documents d WHERE d.collection_id = ? ORDER BY d.name COLLATE NOCASE", (cid,)).fetchall()
    return [dict(r) for r in rows]


def get_document(did: int) -> dict | None:
    with db.conn() as c:
        r = c.execute("SELECT * FROM documents WHERE id = ?", (did,)).fetchone()
    return dict(r) if r else None


def document_chunks(did: int) -> list[dict]:
    with db.conn() as c:
        rows = c.execute("SELECT id, ord, page, line_start, line_end, text FROM chunks WHERE document_id = ? ORDER BY ord",
                         (did,)).fetchall()
    return [dict(r) for r in rows]


def delete_document(did: int) -> None:
    d = get_document(did)
    with db.conn() as c:
        c.execute("DELETE FROM chunks WHERE document_id = ?", (did,))
        c.execute("DELETE FROM documents WHERE id = ?", (did,))
    if d and d.get("path") and str(d["path"]).startswith(str(FILES_DIR)):
        Path(d["path"]).unlink(missing_ok=True)
    _bump()


# ---------------------------------------------------------------- indexation


async def _embed_chunks(chunks: list[dict]) -> list[np.ndarray | None]:
    out: list[np.ndarray | None] = []
    for i in range(0, len(chunks), EMBED_BATCH):
        vecs = await llm.embed([c["text"][:2000] for c in chunks[i:i + EMBED_BATCH]])
        if vecs is None:
            raise RuntimeError("Le modèle d'embedding (nomic-embed-text) est indisponible.")
        out.extend(vecs)
    return out


async def _store_chunks(did: int, cid: int, chunks: list[dict]) -> None:
    vecs = await _embed_chunks(chunks)
    with db.conn() as c:
        c.execute("DELETE FROM chunks WHERE document_id = ?", (did,))
        c.executemany(
            "INSERT INTO chunks (document_id, collection_id, ord, page, line_start, line_end, text, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(did, cid, i, ch.get("page"), ch.get("line_start"), ch.get("line_end"), ch["text"], db.to_blob(v))
             for i, (ch, v) in enumerate(zip(chunks, vecs, strict=False))])
    _bump()


def add_document_record(cid: int, name: str, raw: bytes) -> int:
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    now = time.time()
    with db.conn() as c:
        did = c.execute("INSERT INTO documents (collection_id, name, size, hash, status, created_at) VALUES (?, ?, ?, ?, 'indexing', ?)",
                        (cid, name, len(raw), hashlib.sha1(raw).hexdigest(), now)).lastrowid
        safe = re.sub(r"[^\w.\- ]+", "_", name)[:120]
        path = FILES_DIR / f"{did}_{safe}"
        path.write_bytes(raw)
        c.execute("UPDATE documents SET path = ? WHERE id = ?", (str(path), did))
    return did


async def index_document(did: int) -> None:
    d = get_document(did)
    if not d:
        return
    try:
        raw = Path(d["path"]).read_bytes()
        pages = await asyncio.to_thread(extract_pages, d["name"], raw)
        chunks = chunk_text(pages)
        if not chunks:
            raise Unsupported("Aucun texte trouvé.")
        await _store_chunks(did, d["collection_id"], chunks)
        with db.conn() as c:
            c.execute("UPDATE documents SET status = 'ready', message = NULL, pages = ?, chars = ? WHERE id = ?",
                      (max((p for p, _ in pages if p), default=None), sum(len(t) for _, t in pages), did))
        log.info("document indexé : %s (%d passages)", d["name"], len(chunks))
    except Exception as e:  # noqa: BLE001
        log.warning("indexation impossible pour %s : %s", d["name"], e)
        with db.conn() as c:
            c.execute("UPDATE documents SET status = 'error', message = ? WHERE id = ?", (str(e)[:300], did))


# ---------------------------------------------------------------- projets de code (app/codeprojects.py)
# Importés en fin de module : codeprojects réutilise les constantes et collections définies ci-dessus.
from .codeprojects import (  # noqa: E402,F401 (API publique)
    _code_files, _code_root, _git_url, create_from_files, _index_project, _sync_repo, grep, index_project, list_server_projects, read_file,
    resolve_server_path, tree,
)
