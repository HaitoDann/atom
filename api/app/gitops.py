"""Gestion Git des projets clonés par Atom (mode Code) : statut, branches, commit, push, pull.

Règles :
- uniquement les dépôts clonés par Atom (data/repos) ; les dossiers /projects restent en lecture seule ;
- chaque action vient d'un bouton cliqué par toi, jamais du modèle pendant une discussion ;
- pas de push sur la branche principale du dépôt (Atom travaille sur des branches « atom/… ») ;
- jamais de force-push ; le jeton n'est jamais écrit sur le disque (passé à chaque commande).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import db, library, llm
from .config import DEFAULT_MODEL, GIT_EMAIL, GIT_NAME, GITHUB_TOKEN, PROVIDER

BRANCH_RE = re.compile(r"^(?!/)(?!.*\.\.)(?!.*//)[A-Za-z0-9._/-]{1,100}(?<![./])$")


class GitError(RuntimeError):
    pass


def _repo(cid: int) -> tuple[dict, Path]:
    col = library.get_collection(cid)
    if not col or col["kind"] != "code":
        raise FileNotFoundError("projet")
    src = col.get("source") or ""
    root = library._code_root(col)
    if not src.startswith(("http://", "https://", "git@")) or not (root / ".git").exists():
        raise PermissionError("Ce projet n'est pas un dépôt cloné par Atom (lecture seule).")
    return col, root


def _git(root: Path, *args: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(root), "-c", f"user.name={GIT_NAME}", "-c", f"user.email={GIT_EMAIL}", *args],
                       capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        if GITHUB_TOKEN:
            msg = msg.replace(GITHUB_TOKEN, "***")
        raise GitError(msg[-400:] or "git a échoué")
    return r


def _default_branch(root: Path) -> str:
    r = _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().split("/", 1)[-1]
    for b in ("main", "master"):
        if _git(root, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{b}", check=False).returncode == 0:
            return b
    return "main"


def _current(root: Path) -> str:
    return _git(root, "branch", "--show-current").stdout.strip()


def _ahead(root: Path, branch: str) -> int:
    if _git(root, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}", check=False).returncode == 0:
        rng = [f"refs/remotes/origin/{branch}..HEAD"]
    elif _git(root, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{_default_branch(root)}", check=False).returncode == 0:
        rng = [f"refs/remotes/origin/{_default_branch(root)}..HEAD"]   # branche jamais poussée : par rapport à la principale
    else:
        rng = ["HEAD", "--not", "--remotes"]
    r = _git(root, "rev-list", "--count", *rng, check=False)
    return int(r.stdout.strip() or 0) if r.returncode == 0 else 0


def compare_url(col: dict, base: str, branch: str) -> str | None:
    m = re.match(r"https://github\.com/([^/]+/[^/.]+)", col.get("source") or "")
    return f"https://github.com/{m.group(1)}/compare/{base}...{branch}?expand=1" if m else None


def status(cid: int) -> dict:
    col, root = _repo(cid)
    branch, base = _current(root), _default_branch(root)
    files = []
    for line in _git(root, "status", "--porcelain", "-uall").stdout.splitlines():
        st, path = line[:2], line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        code = st.strip()
        files.append({"path": path, "code": code,
                      "status": {"M": "modifié", "A": "ajouté", "D": "supprimé", "??": "nouveau", "R": "renommé"}.get(code[:1] if code != "??" else code, code)})
    branches = [b.strip() for b in _git(root, "branch", "--format=%(refname:short)").stdout.splitlines() if b.strip()]
    last = _git(root, "log", "-1", "--format=%h%x09%s%x09%ct", check=False).stdout.strip().split("\t")
    ahead = _ahead(root, branch)
    return {"writable": True, "branch": branch, "base": base, "protected": branch == base, "branches": branches,
            "files": files, "ahead": ahead, "token": bool(GITHUB_TOKEN),
            "last": {"hash": last[0], "subject": last[1], "when": int(last[2])} if len(last) == 3 else None,
            "compare": compare_url(col, base, branch) if branch != base else None}


def diff(cid: int, paths: list[str] | None = None) -> str:
    _, root = _repo(cid)
    _git(root, "add", "-N", "--", *(paths or ["."]), check=False)   # inclure les nouveaux fichiers dans le diff
    return _git(root, "diff", "HEAD", "--", *(paths or [])).stdout


def new_branch(cid: int, name: str) -> dict:
    _, root = _repo(cid)
    name = name.strip()
    if not BRANCH_RE.match(name):
        raise ValueError("Nom de branche invalide (lettres, chiffres, - _ . /).")
    _git(root, "switch", "-c", name)   # les modifications en cours suivent sur la nouvelle branche
    return status(cid)


def switch(cid: int, name: str) -> dict:
    _, root = _repo(cid)
    r = _git(root, "switch", name, check=False)
    if r.returncode != 0:
        msg = r.stderr or r.stdout
        if "would be overwritten" in msg:
            raise GitError("Des modifications en cours seraient perdues : fais un commit ou annule-les d'abord.")
        raise GitError(msg.strip()[-300:])
    return status(cid)


def commit(cid: int, message: str, paths: list[str]) -> dict:
    _, root = _repo(cid)
    message = message.strip()
    if len(message) < 3:
        raise ValueError("Message de commit trop court.")
    if not paths:
        raise ValueError("Choisis au moins un fichier.")
    _git(root, "reset", "-q")                 # on ne commite que la sélection
    _git(root, "add", "-A", "--", *paths)
    if not _git(root, "diff", "--cached", "--name-only").stdout.strip():
        raise ValueError("Rien à commiter dans la sélection.")
    _git(root, "commit", "-q", "-m", message)
    return status(cid)


def push(cid: int) -> dict:
    col, root = _repo(cid)
    branch, base = _current(root), _default_branch(root)
    if not branch:
        raise GitError("Aucune branche active.")
    if branch == base:
        raise PermissionError(f"Atom ne pousse pas sur « {base} » : crée d'abord une branche (ex. atom/ma-modif).")
    if not GITHUB_TOKEN:
        raise PermissionError("Ajoute un jeton GitHub avec droit d'écriture (ATOM_GITHUB_TOKEN) dans .env.")
    r = _git(root, "push", library._git_url(col["source"]), f"HEAD:refs/heads/{branch}", timeout=300, check=False)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").replace(GITHUB_TOKEN, "***")
        if "403" in msg or "denied" in msg.lower() or "Authentication" in msg:
            raise PermissionError("GitHub refuse : le jeton n'a pas le droit d'écriture sur ce dépôt (Contents: Read and write).")
        if "rejected" in msg or "non-fast-forward" in msg:
            raise GitError("La branche a changé sur GitHub : fais « Récupérer » d'abord.")
        raise GitError(msg.strip()[-300:])
    _git(root, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")
    out = status(cid)
    out["pushed"] = branch
    return out


def discard_all(cid: int) -> dict:
    _, root = _repo(cid)
    _git(root, "reset", "-q", "--hard")
    _git(root, "clean", "-fdq")
    return status(cid)


async def suggest_message(cid: int, paths: list[str]) -> str:
    d = diff(cid, paths)[:12000]
    if not d.strip():
        raise ValueError("Aucune modification dans la sélection.")
    if PROVIDER == "mock":
        return "Mise à jour de " + ", ".join(paths[:3])
    messages = [
        {"role": "system", "content": "Tu écris des messages de commit Git. Une ligne de titre de 72 caractères maximum, "
                                      "à l'impératif, en français, sans point final ; puis, si utile, une ligne vide et 1 à 3 puces courtes. "
                                      "Réponds uniquement avec le message, sans balise ni bloc de code."},
        {"role": "user", "content": f"Diff :\n```diff\n{d}\n```"},
    ]
    out = []   # toujours en local : le diff ne sort pas du serveur pour un simple message
    async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, messages):
        out.append(t)
    msg = re.sub(r"^\[[a-z_]+\]\s*", "", "".join(out).strip()).strip("`").strip()
    return msg[:2000]
