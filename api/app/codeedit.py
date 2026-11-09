"""Mode Code, étape 2 : Atom propose des modifications, tu valides fichier par fichier.

- propose() : le modèle réécrit la sélection (ou le fichier entier s'il est court) selon ta consigne ;
  le serveur calcule le diff (difflib) — le modèle ne touche jamais au disque.
- apply() : écrit la proposition, uniquement dans les clones Git gérés par Atom (data/repos) ;
  les dossiers serveur (/projects) sont montés en lecture seule → patch à télécharger.
- changes() / revert() : modifications locales (git status) et retour à la version du dépôt.
"""

from __future__ import annotations

import difflib
import re
import secrets
import subprocess
import time
from pathlib import Path

from . import db, hybrid, library, llm
from .config import DEFAULT_MODEL, PROVIDER

MAX_WHOLE_LINES = 400
_proposals: dict[str, dict] = {}

SYSTEM = (
    "Tu es un développeur expérimenté. On te donne un extrait de code et une consigne. "
    "Réécris l'extrait en appliquant la consigne, sans rien changer d'autre (garde le style, l'indentation, "
    "les commentaires utiles). Réponds avec UNE ligne d'explication, puis l'extrait complet réécrit dans un seul "
    "bloc ``` ```. N'ajoute rien après le bloc."
)


def writable(col: dict) -> bool:
    src = col.get("source") or ""
    return src.startswith(("http://", "https://", "git@", "atom:")) and (library._code_root(col) / ".git").exists()


def _root_and_path(cid: int, rel: str) -> tuple[dict, Path, Path]:
    col = library.get_collection(cid)
    if not col or col["kind"] != "code":
        raise FileNotFoundError("projet")
    root = library._code_root(col).resolve()
    p = (root / rel).resolve()
    if not str(p).startswith(str(root) + "/") or not p.is_file():
        raise FileNotFoundError(rel)
    return col, root, p


def _extract_code(reply: str) -> tuple[str, str]:
    m = re.search(r"```[^\n]*\n(.*?)```", reply, re.S)
    if not m:
        m = re.search(r"```[^\n]*\n(.*)$", reply, re.S)   # bloc non refermé (réponse coupée)
    if not m:
        raise ValueError("La réponse ne contient pas de code exploitable. Reformule la consigne.")
    note = reply[: m.start()].strip()
    note = re.sub(r"^\[[a-z_]+\]\s*", "", note)            # balise d'émotion éventuelle
    return note[:400], m.group(1)


async def _ask(messages: list[dict], engine: str) -> tuple[str, str]:
    use_remote = (engine == "remote" and hybrid.configured() and hybrid.quota_left() > 0
                  and hybrid.settings().get("allow_docs"))   # le code ne sort que si tu l'as autorisé
    out = []
    if use_remote:
        async for t in hybrid.stream(messages, sensitive=True):
            out.append(t)
        return "".join(out), hybrid.last_used.get("name") or hybrid.name()
    if PROVIDER == "mock":
        code = messages[-1]["content"].split("```", 2)[1].split("\n", 1)[1]
        return f"(mode test) Ajout d'un commentaire.\n```\n# modifié par Atom\n{code}```", "mock"
    async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, messages):
        out.append(t)
    return "".join(out), "local"


async def propose(cid: int, rel: str, instruction: str, start: int | None, end: int | None, engine: str = "local") -> dict:
    col, root, p = _root_and_path(cid, rel)
    old = p.read_text("utf-8")
    lines = old.splitlines(keepends=True)
    if start is None or end is None:
        if len(lines) > MAX_WHOLE_LINES:
            raise ValueError(f"Fichier long ({len(lines)} lignes) : sélectionne la partie à modifier.")
        start, end = 1, max(1, len(lines))
    start, end = max(1, start), min(len(lines), end) if lines else 1
    region = "".join(lines[start - 1:end])
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Fichier : {rel} (lignes {start} à {end})\n\nConsigne : {instruction.strip()}\n\n```\n{region}```"},
    ]
    reply, by = await _ask(messages, engine)
    note, new_region = _extract_code(reply)
    if region.endswith("\n") and not new_region.endswith("\n"):
        new_region += "\n"
    new = "".join(lines[:start - 1]) + new_region + "".join(lines[end:])
    if new == old:
        raise ValueError("Atom n'a proposé aucun changement.")
    diff = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        f"a/{rel}", f"b/{rel}", n=3))
    if not diff.endswith("\n"):
        diff += "\n"
    pid = secrets.token_hex(8)
    for k in [k for k, v in _proposals.items() if time.time() - v["at"] > 3600]:
        _proposals.pop(k, None)
    _proposals[pid] = {"cid": cid, "path": rel, "old": old, "new": new, "at": time.time()}
    added = sum(1 for x in diff.splitlines() if x.startswith("+") and not x.startswith("+++"))
    removed = sum(1 for x in diff.splitlines() if x.startswith("-") and not x.startswith("---"))
    return {"id": pid, "path": rel, "diff": diff, "note": note, "by": by, "added": added, "removed": removed,
            "writable": writable(col), "range": [start, end]}


def apply(pid: str) -> dict:
    pr = _proposals.get(pid)
    if not pr:
        raise KeyError("Proposition expirée : redemande-la.")
    col, root, p = _root_and_path(pr["cid"], pr["path"])
    if not writable(col):
        raise PermissionError("Ce projet est en lecture seule (dossier serveur) : télécharge le patch.")
    if p.read_text("utf-8") != pr["old"]:
        raise RuntimeError("Le fichier a changé depuis la proposition : redemande-la.")
    p.write_text(pr["new"], "utf-8")
    _proposals.pop(pid, None)
    return {"path": pr["path"], "content": pr["new"]}


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-300:])
    return r.stdout


def changes(cid: int) -> dict:
    col = library.get_collection(cid)
    if not col or col["kind"] != "code":
        raise FileNotFoundError("projet")
    if not writable(col):
        return {"writable": False, "files": [], "diff": ""}
    root = library._code_root(col)
    files = []
    for line in _git(root, "status", "--porcelain").splitlines():
        st, path = line[:2].strip(), line[3:].strip().strip('"')
        files.append({"path": path, "status": {"M": "modifié", "A": "ajouté", "D": "supprimé", "??": "nouveau"}.get(st, st)})
    return {"writable": True, "files": files, "diff": _git(root, "diff") if files else ""}


def revert(cid: int, rel: str) -> None:
    col, root, p = _root_and_path(cid, rel)
    if not writable(col):
        raise PermissionError("lecture seule")
    _git(root, "checkout", "--", rel)
