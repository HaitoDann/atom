"""Bibliothèque : tes documents et tes projets de code, découpés et indexés.

- Collections de documents (PDF, Word, texte, Markdown…) ajoutés depuis l'interface.
- Projets de code : un dépôt GitHub (cloné) ou un dossier du serveur (/projects), en lecture seule.
- Chaque fichier est découpé en passages, chaque passage reçoit un embedding (nomic-embed-text).
- À chaque message, les passages les plus proches sont donnés au modèle, avec leur source.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

import numpy as np

from . import db, llm, ocr
from .config import DATA_DIR, GITHUB_TOKEN, PROJECTS_DIR

log = logging.getLogger("atom.library")
FILES_DIR = DATA_DIR / "library"
REPOS_DIR = DATA_DIR / "repos"

CHUNK, OVERLAP = 1100, 180          # documents : caractères
CODE_LINES, CODE_OVERLAP = 60, 8     # code : lignes
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


# ---------------------------------------------------------------- extraction de texte


class Unsupported(ValueError):
    pass


def extract_pages(name: str, raw: bytes) -> list[tuple[int | None, str]]:
    """[(page, texte)] — page = None pour les formats sans pagination."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "pdf" or raw[:5] == b"%PDF-":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        allp = [(i + 1, (p.extract_text() or "").strip()) for i, p in enumerate(reader.pages[:2000])]
        # Pages scannées (pas ou presque pas de texte) : lecture par OCR.
        scanned = {n for n, t in allp if len(t) < 40}
        if scanned and ocr.pdf_available():
            got = dict(ocr.pdf_pages(raw, only=scanned))
            allp = [(n, got.get(n, t)) for n, t in allp]
        pages = [p for p in allp if p[1]]
        if not pages:
            raise Unsupported("PDF sans texte (document scanné ?) et lecture des scans indisponible sur ce serveur."
                              if not ocr.pdf_available() else "Aucun texte lisible, même par OCR.")
        return pages
    if ext == "docx":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.getinfo("word/document.xml").file_size > 40 * 1024 * 1024:   # archive piégée (« zip bomb »)
                raise Unsupported("Document trop volumineux une fois décompressé.")
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<w:tab/>", "\t", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        import html as _h
        return [(None, _h.unescape(text).strip())]
    if ext in {"odt"}:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.getinfo("content.xml").file_size > 40 * 1024 * 1024:
                raise Unsupported("Document trop volumineux une fois décompressé.")
            xml = z.read("content.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</text:p>|</text:h>", "\n", xml)
        import html as _h
        return [(None, _h.unescape(re.sub(r"<[^>]+>", "", xml)).strip())]
    if ext in ocr.IMAGE_EXT:
        if not ocr.available():
            raise Unsupported("Lecture des images (OCR) indisponible sur ce serveur.")
        text = ocr.image_text(raw, ext)
        if not text:
            raise Unsupported("Aucun texte trouvé dans l'image.")
        return [(None, text)]
    if ext == "heic":
        raise Unsupported("Format HEIC non pris en charge : exporte l'image en JPEG.")
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if "\x00" in text[:4000]:
        raise Unsupported("Format non pris en charge (fichier binaire).")
    if ext in {"html", "htm"}:
        from .search import page_text
        text = page_text(text, limit=2_000_000)
    return [(None, text)]


def chunk_text(pages: list[tuple[int | None, str]]) -> list[dict]:
    out = []
    for page, text in pages:
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        i = 0
        while i < len(text):
            end = min(len(text), i + CHUNK)
            if end < len(text):   # couper sur une fin de paragraphe ou de phrase si possible
                cut = max(text.rfind("\n\n", i + CHUNK // 2, end), text.rfind(". ", i + CHUNK // 2, end))
                if cut > i:
                    end = cut + 1
            piece = text[i:end].strip()
            if piece:
                out.append({"page": page, "text": piece})
            if end >= len(text):
                break
            i = max(end - OVERLAP, i + 1)
    return out


def chunk_code(path: str, text: str) -> list[dict]:
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        j = min(len(lines), i + CODE_LINES)
        body = "\n".join(lines[i:j]).strip()
        if body:
            out.append({"line_start": i + 1, "line_end": j, "text": f"# {path} (lignes {i + 1}-{j})\n{body}"})
        if j >= len(lines):
            break
        i = j - CODE_OVERLAP
    return out


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


# ---------------------------------------------------------------- projets de code


def _git_url(url: str) -> str:
    if GITHUB_TOKEN and url.startswith("https://github.com/"):
        return url.replace("https://", f"https://x-access-token:{GITHUB_TOKEN}@", 1)
    return url


def _code_root(col: dict) -> Path:
    src = col["source"] or ""
    if src.startswith(("http://", "https://", "git@")):
        return REPOS_DIR / str(col["id"])
    p = Path(src)
    if not p.is_absolute():
        p = PROJECTS_DIR / src
    return p


def resolve_server_path(src: str) -> Path:
    """Les dossiers serveur sont limités à PROJECTS_DIR (montage en lecture seule)."""
    p = (PROJECTS_DIR / src.lstrip("/").removeprefix(str(PROJECTS_DIR).lstrip("/")).lstrip("/")).resolve()
    if not p.is_relative_to(PROJECTS_DIR.resolve()):   # vrai test de chemin (pas un simple préfixe de texte)
        raise ValueError(f"Le dossier doit être dans {PROJECTS_DIR}.")
    if not p.is_dir():
        raise ValueError(f"Dossier introuvable : {p}")
    return p


def list_server_projects() -> list[str]:
    if not PROJECTS_DIR.is_dir():
        return []
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and not p.name.startswith("."))


def _git_err(r: subprocess.CompletedProcess) -> str:
    msg = (r.stderr or r.stdout or "")
    return (msg.replace(GITHUB_TOKEN, "***") if GITHUB_TOKEN else msg).strip()[-300:]


def _sync_repo(col: dict) -> Path:
    root = _code_root(col)
    src = col["source"]
    if src.startswith(("http://", "https://", "git@")):
        if (root / ".git").exists():
            g = ["git", "-C", str(root)]
            subprocess.run([*g, "remote", "set-url", "origin", src], capture_output=True, timeout=30)   # pas de jeton sur le disque
            branch = subprocess.run([*g, "branch", "--show-current"], capture_output=True, text=True, timeout=30).stdout.strip()
            # sans --depth : dans un clone superficiel, git ne récupère que ce qui manque depuis notre dernier commit
            r = subprocess.run([*g, "fetch", _git_url(src), f"+refs/heads/{branch}:refs/remotes/origin/{branch}"],
                               capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                r = subprocess.run([*g, "merge", "--ff-only", f"refs/remotes/origin/{branch}"], capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                msg = _git_err(r)
                if "couldn't find remote ref" in msg:
                    pass   # branche créée par Atom, pas encore poussée : rien à récupérer
                elif "would be overwritten" in msg or "fast-forward" in msg or "diverg" in msg:
                    raise RuntimeError("Mise à jour impossible : tes modifications locales ou commits non poussés "
                                       "entrent en conflit avec GitHub. Pousse-les sur une branche ou annule-les.")
                else:
                    raise RuntimeError(msg)
        else:
            shutil.rmtree(root, ignore_errors=True)
            root.parent.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(["git", "clone", "--depth", "1", _git_url(src), str(root)],
                               capture_output=True, text=True, timeout=600)
            denied = lambda m: any(x in m for x in ("403", "not granted", "Authentication", "could not read Username", "denied"))
            if r.returncode != 0 and GITHUB_TOKEN and denied(_git_err(r)):
                # Jeton limité à d'autres dépôts : un dépôt public se clone sans jeton.
                shutil.rmtree(root, ignore_errors=True)
                r2 = subprocess.run(["git", "clone", "--depth", "1", src, str(root)], capture_output=True, text=True, timeout=600,
                                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
                if r2.returncode == 0:
                    r = r2
                else:
                    raise RuntimeError("Accès refusé : ton jeton GitHub ne couvre pas ce dépôt (privé). Sur github.com → Settings → "
                                       "Developer settings → Fine-grained tokens → ton jeton → Repository access : ajoute ce dépôt.")
            if r.returncode != 0:
                msg = _git_err(r)
                if denied(msg) or "not found" in msg.lower():
                    msg = ("Dépôt introuvable ou privé : vérifie l'adresse, et pour un dépôt privé ajoute-le à ton jeton "
                           "(ATOM_GITHUB_TOKEN, Repository access).")
                raise RuntimeError(msg)
            subprocess.run(["git", "-C", str(root), "remote", "set-url", "origin", src], capture_output=True, timeout=30)
    return root


def _code_files(root: Path) -> list[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            ext = f.rsplit(".", 1)[-1].lower() if "." in f else f.lower()
            if ext not in CODE_EXT or SKIP_FILES.search(f):
                continue
            p = Path(dirpath) / f
            try:
                if p.stat().st_size > MAX_CODE_FILE:
                    continue
            except OSError:
                continue
            files.append(p)
            if len(files) >= MAX_CODE_FILES:
                return files
    return files


def tree(cid: int, max_lines: int = 120) -> str:
    """Arborescence résumée d'un projet (pour l'interface et le prompt)."""
    with db.conn() as c:
        paths = [r["path"] for r in c.execute("SELECT path FROM documents WHERE collection_id = ? ORDER BY path", (cid,))]
    dirs: dict[str, int] = {}
    for p in paths:
        d = p.rsplit("/", 1)[0] if "/" in p else "."
        dirs[d] = dirs.get(d, 0) + 1
    lines = [f"{d}/ ({n} fichier{'s' if n > 1 else ''})" for d, n in sorted(dirs.items())]
    return "\n".join(lines[:max_lines]) + ("\n…" if len(lines) > max_lines else "")


PROGRESS: dict[int, dict] = {}   # cid → {phase, done, total, started}
EMBED_BATCH = int(os.getenv("ATOM_EMBED_BATCH", "64"))


def _progress(cid: int, phase: str, done: int = 0, total: int = 0) -> None:
    p = PROGRESS.setdefault(cid, {"started": time.time()})
    p.update(phase=phase, done=done, total=total)


_index_locks: dict[int, asyncio.Lock] = {}


async def index_project(cid: int) -> None:
    """Une seule indexation à la fois par projet (mise à jour Git, application de l'agent, etc.)."""
    lock = _index_locks.setdefault(cid, asyncio.Lock())
    if lock.locked():
        log.info("indexation du projet %s déjà en cours : la demande attend son tour", cid)
    async with lock:
        await _index_project(cid)


async def _index_project(cid: int) -> None:
    """Deux temps : 1) les fichiers sont enregistrés (le projet est tout de suite consultable),
    2) les passages sont vectorisés par gros lots, avec progression (c'est la partie lente sur CPU)."""
    col = get_collection(cid)
    if not col:
        return
    PROGRESS.pop(cid, None)
    _progress(cid, "clone")
    set_collection(cid, status="indexing", message="Récupération du code…")
    try:
        t0 = time.time()
        root = await asyncio.to_thread(_sync_repo, col)
        files = await asyncio.to_thread(_code_files, root)
        if not files:
            raise RuntimeError("Aucun fichier de code lisible trouvé.")
        log.info("projet %s récupéré en %.1f s (%d fichiers)", col["name"], time.time() - t0, len(files))
        _progress(cid, "read", 0, len(files))
        set_collection(cid, message=f"Lecture de {len(files)} fichiers…")
        with db.conn() as c:
            known = {r["path"]: dict(r) for r in c.execute("SELECT id, path, hash FROM documents WHERE collection_id = ?", (cid,))}
        seen, todo = set(), []   # todo : [(did, chunks)]
        with db.conn() as c:
            for f in files:
                rel = str(f.relative_to(root))
                seen.add(rel)
                try:
                    raw = f.read_bytes()
                except OSError:
                    continue
                h = hashlib.sha1(raw).hexdigest()
                if rel in known and known[rel]["hash"] == h:
                    continue   # inchangé
                text = raw.decode("utf-8", "ignore")
                if "\x00" in text[:2000]:
                    continue
                if rel in known:
                    did = known[rel]["id"]
                    c.execute("UPDATE documents SET hash = ?, size = ?, chars = ?, status = 'ready' WHERE id = ?",
                              (h, len(raw), len(text), did))
                else:
                    did = c.execute("INSERT INTO documents (collection_id, name, path, size, chars, hash, status, created_at) "
                                    "VALUES (?, ?, ?, ?, ?, ?, 'ready', ?)",
                                    (cid, f.name, rel, len(raw), len(text), h, time.time())).lastrowid
                chunks = chunk_code(rel, text)
                if chunks:
                    todo.append((did, chunks))
            for rel, d in known.items():   # fichiers supprimés du projet
                if rel not in seen:
                    c.execute("DELETE FROM chunks WHERE document_id = ?", (d["id"],))
                    c.execute("DELETE FROM documents WHERE id = ?", (d["id"],))
        _bump()
        # Vectorisation : tous les passages à la suite, par lots de EMBED_BATCH (moins d'allers-retours).
        flat = [(did, ch) for did, chunks in todo for ch in chunks]
        total = len(flat)
        _progress(cid, "embed", 0, total)
        t1 = time.time()
        vecs: list = []
        for i in range(0, total, EMBED_BATCH):
            batch = flat[i:i + EMBED_BATCH]
            v = await llm.embed([ch["text"][:2000] for _, ch in batch])
            if v is None:
                raise RuntimeError("Le modèle d'embedding (nomic-embed-text) est indisponible.")
            vecs.extend(v)
            _progress(cid, "embed", len(vecs), total)
            set_collection(cid, message=f"Indexation : {len(vecs)}/{total} passages")
        pos = 0
        with db.conn() as c:
            for did, chunks in todo:
                c.execute("DELETE FROM chunks WHERE document_id = ?", (did,))
                c.executemany(
                    "INSERT INTO chunks (document_id, collection_id, ord, page, line_start, line_end, text, embedding) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(did, cid, k, ch.get("page"), ch.get("line_start"), ch.get("line_end"), ch["text"], db.to_blob(vecs[pos + k]))
                     for k, ch in enumerate(chunks)])
                pos += len(chunks)
        _bump()
        dt = time.time() - t1
        set_collection(cid, status="ready", message=f"{len(files)} fichiers indexés.")
        log.info("projet %s indexé : %d fichiers (%d mis à jour), %d passages en %.1f s (%.0f/s)",
                 col["name"], len(files), len(todo), total, dt, total / dt if dt else 0)
    except Exception as e:  # noqa: BLE001
        log.warning("indexation du projet %s impossible : %s", col["name"], e)
        set_collection(cid, status="error", message=str(e)[:300])
    finally:
        PROGRESS.pop(cid, None)


def read_file(cid: int, rel: str) -> str:
    col = get_collection(cid)
    if not col or col["kind"] != "code":
        raise FileNotFoundError(rel)
    root = _code_root(col).resolve()
    p = (root / rel).resolve()
    if p == root or not p.is_relative_to(root) or not p.is_file():
        raise FileNotFoundError(rel)
    return p.read_text("utf-8", "ignore")[:400_000]


def grep(cid: int, q: str, limit: int = 300) -> list[dict]:
    col = get_collection(cid)
    if not col or col["kind"] != "code":
        raise FileNotFoundError(cid)
    root = _code_root(col).resolve()
    with db.conn() as c:
        paths = [r["path"] for r in c.execute("SELECT path FROM documents WHERE collection_id = ? ORDER BY path", (cid,))]
    ql = q.lower()
    out = []
    for rel in paths:
        p = root / rel
        try:
            text = p.read_text("utf-8", "ignore")
        except OSError:
            continue
        if ql not in text.lower():
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if ql in line.lower():
                out.append({"path": rel, "line": n, "text": line.strip()[:200]})
                if len(out) >= limit:
                    return out
    return out
