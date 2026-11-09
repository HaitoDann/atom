"""Projets de code de la bibliothèque : dépôts Git clonés ou dossiers du serveur, arborescence,
lecture et recherche de fichiers, indexation incrémentale du code.

Séparé de library.py (documents, collections, recherche sémantique), qui réexporte ces fonctions.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import db, llm
from .config import GITHUB_TOKEN, PROJECTS_DIR
from .extract import chunk_code
from .library import (
    CODE_EXT, EMBED_BATCH, MAX_CODE_FILE, MAX_CODE_FILES, PROGRESS, REPOS_DIR, SKIP_DIRS, SKIP_FILES, _bump, get_collection,
    set_collection,
)

log = logging.getLogger("atom.library")


def _git_url(url: str) -> str:
    if GITHUB_TOKEN and url.startswith("https://github.com/"):
        return url.replace("https://", f"https://x-access-token:{GITHUB_TOKEN}@", 1)
    return url


def _code_root(col: dict) -> Path:
    src = col["source"] or ""
    if src.startswith(("http://", "https://", "git@", "atom:")):   # atom: projet créé par Atom (fichiers d'une réponse)
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


# ---------------------------------------------------------------- projets créés par Atom (fichiers d'une réponse)

SAFE_PATH = re.compile(r"^(?!/)(?!.*\.\.)[\w .@+/-]{1,200}$")


def create_from_files(name: str, files: list[dict]) -> int:
    """Crée un projet modifiable (dépôt Git local) à partir de fichiers [{path, content}] : il s'ouvre ensuite dans
    le mode Code (lecture, modifications validées, agent, tests en bac à sable)."""
    from . import library
    clean = []
    for f in files:
        path = str(f.get("path", "")).strip()
        while path.startswith("./"):
            path = path[2:]
        if not SAFE_PATH.match(path) or path.startswith(".git"):
            raise ValueError(f"nom de fichier refusé : {path!r}")
        clean.append((path, str(f.get("content", ""))))
    if not clean:
        raise ValueError("aucun fichier à enregistrer")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "projet"
    cid = library.create_collection(name.strip()[:80] or "Projet", "code", f"atom:{slug}")
    root = REPOS_DIR / str(cid)
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    for path, content in clean:
        dest = (root / path).resolve()
        if root.resolve() not in dest.parents:
            raise ValueError(f"nom de fichier refusé : {path!r}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    g = ["git", "-C", str(root), "-c", "user.name=Atom", "-c", "user.email=atom@localhost"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], capture_output=True, timeout=30)
    subprocess.run([*g, "add", "-A"], capture_output=True, timeout=30)
    subprocess.run([*g, "commit", "-q", "-m", "Version générée par Atom"], capture_output=True, timeout=30)
    log.info("projet %s créé à partir de %d fichier(s)", name, len(clean))
    return cid
