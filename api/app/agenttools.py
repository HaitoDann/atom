"""Outils de l'agent de code : espace de travail (lecture disque + modifications en mémoire),
définition des outils, permissions, validation des arguments et exécution.
"""

from __future__ import annotations

import difflib

from . import db, library, sandbox

READ_LINES = 250


class Workspace:
    """Vue du projet : disque en lecture + modifications en mémoire."""

    def __init__(self, cid: int):
        col = library.get_collection(cid)
        if not col or col["kind"] != "code":
            raise FileNotFoundError("projet")
        self.cid, self.col = cid, col
        self.root = library._code_root(col).resolve()
        with db.conn() as c:
            self.paths = {r["path"] for r in c.execute("SELECT path FROM documents WHERE collection_id = ?", (cid,))}
        self.changes: dict[str, str] = {}     # chemin → nouveau contenu
        self.original: dict[str, str | None] = {}   # chemin → contenu d'origine (None = nouveau fichier)
        self.read_ok: set[str] = set()
        self.stopped = lambda: False
        self.perms = {"read", "write", "test"}

    def _safe(self, rel: str) -> str:
        rel = (rel or "").strip().replace("\\", "/")
        # « ./src/a.py », « /src/ », « . » → chemins relatifs propres
        parts = [x for x in rel.split("/") if x not in ("", ".")]
        rel = "/".join(parts)
        p = (self.root / rel).resolve()
        if rel and (not str(p).startswith(str(self.root) + "/") or "/.git/" in f"/{rel}/"):
            raise ValueError("chemin hors du projet")
        return rel

    def text(self, rel: str) -> str | None:
        if rel in self.changes:
            return self.changes[rel]
        p = self.root / rel
        if not p.is_file():
            return None
        return p.read_text("utf-8", "ignore")

    def all_paths(self) -> list[str]:
        return sorted(self.paths | set(self.changes))

    # ---- outils
    def t_list(self, d: str = "") -> str:
        d = self._safe(d).rstrip("/")
        pre = d + "/" if d else ""
        entries: dict[str, str] = {}
        for p in self.all_paths():
            if not p.startswith(pre):
                continue
            rest = p[len(pre):]
            if "/" in rest:
                entries.setdefault(rest.split("/", 1)[0] + "/", "dossier")
            else:
                entries[rest] = "fichier"
        if not entries:
            return f"Dossier vide ou inexistant : {d or '.'}"
        lines = sorted(entries)
        return "\n".join(lines[:300]) + ("\n…" if len(lines) > 300 else "")

    def t_read(self, path: str, start: int | None = None, end: int | None = None) -> str:
        rel = self._safe(path)
        t = self.text(rel)
        if t is None:
            near = [p for p in self.all_paths() if p.endswith("/" + rel.split("/")[-1]) or p == rel.split("/")[-1]][:5]
            return f"Fichier introuvable : {rel}" + (f". Peut-être : {', '.join(near)}" if near else "")
        lines = t.split("\n")
        a = max(1, int(start or 1))
        b = min(len(lines), int(end or a + READ_LINES - 1), a + READ_LINES - 1)
        self.read_ok.add(rel)
        body = "\n".join(f"{i:>5}| {lines[i - 1]}" for i in range(a, b + 1))
        more = f"\n… ({len(lines)} lignes au total ; lis la suite avec start={b + 1})" if b < len(lines) else ""
        return f"{rel} (lignes {a}-{b} sur {len(lines)})\n{body}{more}"

    def t_search(self, query: str) -> str:
        q = (query or "").strip()
        if len(q) < 2:
            return "Recherche trop courte."
        out = []
        for rel in self.all_paths():
            t = self.text(rel)
            if not t:
                continue
            for i, line in enumerate(t.split("\n"), 1):
                if q.lower() in line.lower():
                    out.append(f"{rel}:{i}: {line.strip()[:160]}")
                    if len(out) >= 60:
                        return "\n".join(out) + "\n… (résultats tronqués, affine la recherche)"
        return "\n".join(out) or f"Aucun résultat pour « {q} »."

    def _record(self, rel: str, new: str) -> None:
        if rel not in self.original:
            self.original[rel] = self.text(rel)   # état du disque, avant toute modification de l'agent
        self.changes[rel] = new

    def t_edit(self, path: str, old: str, new: str) -> str:
        rel = self._safe(path)
        t = self.text(rel)
        if t is None:
            return f"Fichier introuvable : {rel} (utilise « write » pour le créer)."
        if rel not in self.read_ok:
            return f"Lis d'abord {rel} (outil read) avant de le modifier."
        if not old:
            return "« old » est vide."
        n = t.count(old)
        if n == 0:
            # aide : la ligne la plus proche
            first = old.strip().split("\n")[0].strip()
            hint = next((f"ligne {i}: {l.strip()[:120]}" for i, l in enumerate(t.split("\n"), 1) if first and first[:30] in l), "")
            return f"« old » introuvable dans {rel} : copie le passage à l'identique (relis le fichier)." + (f" Proche : {hint}" if hint else "")
        if n > 1:
            return f"« old » apparaît {n} fois dans {rel} : ajoute des lignes autour pour le rendre unique."
        self._record(rel, t.replace(old, new, 1))
        return f"OK : {rel} modifié ({old.count(chr(10)) + 1} ligne(s) remplacée(s) par {new.count(chr(10)) + 1})."

    def t_write(self, path: str, content: str) -> str:
        rel = self._safe(path)
        if not rel:
            return "Chemin manquant."
        t = self.text(rel)
        if t is not None and rel not in self.read_ok:
            return f"{rel} existe déjà : lis-le d'abord, et préfère « edit » pour un fichier existant."
        if t is not None and len(t.split("\n")) > 300:
            return f"{rel} est long : utilise « edit » pour modifier seulement le passage utile."
        self._record(rel, content if content.endswith("\n") else content + "\n")
        self.read_ok.add(rel)
        return f"OK : {rel} {'réécrit' if t is not None else 'créé'} ({content.count(chr(10)) + 1} lignes)."

    # ---- résultat
    def diffs(self) -> list[dict]:
        out = []
        for rel in sorted(self.changes):
            old = self.original.get(rel)
            new = self.changes[rel]
            if old == new:
                continue
            d = "".join(difflib.unified_diff((old or "").splitlines(keepends=True), new.splitlines(keepends=True),
                                             "/dev/null" if old is None else f"a/{rel}", f"b/{rel}", n=3))
            if not d.endswith("\n"):
                d += "\n"
            out.append({"path": rel, "new_file": old is None, "diff": d,
                        "added": sum(1 for x in d.splitlines() if x.startswith("+") and not x.startswith("+++")),
                        "removed": sum(1 for x in d.splitlines() if x.startswith("-") and not x.startswith("---"))})
        return out


TEST_TOOL = {"type": "function", "function": {"name": "test", "description":
    "Lance les tests du projet dans un bac à sable sans réseau, AVEC tes modifications en cours. Renvoie le code de sortie et la fin de la sortie.",
    "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "commande (facultatif) ; par défaut, celle du projet"}}, "required": []}}}
TEST_TEXT = """
- {{"tool": "test", "command": "facultatif"}} : lancer les tests dans un bac à sable sans réseau, avec tes modifications"""
TEST_NOTE = """Bac à sable disponible : après avoir modifié du code, lance « test ». Si les tests échouent à cause de tes
changements, corrige puis relance (3 essais au plus). Commande par défaut : {cmd}

"""


def tools(perms: set[str] | None = None) -> list[dict]:
    perms = perms or {"read", "write", "test"}
    out = [t for t in TOOLS if TOOL_PERMS[t["function"]["name"]] in perms]
    return out + ([TEST_TOOL] if sandbox.enabled() and "test" in perms else [])


TOOLS = [
    {"type": "function", "function": {"name": "list", "description": "Liste les fichiers et sous-dossiers d'un dossier du projet.",
     "parameters": {"type": "object", "properties": {"dir": {"type": "string", "description": "chemin relatif, \"\" pour la racine"}}, "required": []}}},
    {"type": "function", "function": {"name": "read", "description": "Lit des lignes d'un fichier (numérotées, 250 au plus par appel).",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search", "description": "Cherche un texte exact dans tout le projet (fichier:ligne).",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "edit", "description": "Remplace un passage exact (unique dans le fichier, déjà lu) par un nouveau texte.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}, "required": ["path", "old", "new"]}}},
    {"type": "function", "function": {"name": "write", "description": "Crée un fichier, ou réécrit entièrement un fichier court déjà lu.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "done", "description": "Termine : résumé des changements, ou réponse détaillée (Markdown) si la tâche est une question.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
]

NATIVE_NOTE = """
(Mode outils natifs : utilise directement les fonctions list, read, search, edit, write et done — pas de bloc ```action```.
Écris ta réflexion courte dans le texte de ta réponse, et appelle un outil à chaque tour. Termine toujours par done.)"""


# Permissions par outil : une tâche en lecture seule n'a ni « edit », ni « write », ni « test ».
TOOL_PERMS = {"list": "read", "read": "read", "search": "read", "edit": "write", "write": "write", "test": "test", "done": "read"}
LIMITS = {"path": 500, "dir": 500, "query": 300, "old": 200_000, "new": 200_000, "content": 400_000, "command": 300, "summary": 20_000}


def validate(tool: str, a: dict, perms: set[str]) -> str | None:
    """Refuse les appels mal formés ou non autorisés (renvoie le motif, ou None si tout va bien)."""
    if tool not in TOOL_PERMS:
        return f"Outil inconnu : {tool}."
    if TOOL_PERMS[tool] not in perms:
        return f"Outil « {tool} » non autorisé pour cette tâche (lecture seule)."
    if not isinstance(a, dict):
        return "Arguments invalides."
    for k, v in a.items():
        if k in ("start", "end"):
            if v is not None and not (isinstance(v, int) and 0 < v < 10_000_000):
                return f"« {k} » doit être un numéro de ligne."
        elif k in LIMITS:
            if not isinstance(v, str):
                return f"« {k} » doit être du texte."
            if len(v) > LIMITS[k]:
                return f"« {k} » est trop long ({len(v)} caractères, {LIMITS[k]} au plus)."
            if k in ("path", "dir") and ("\x00" in v or v.strip().startswith("~")):
                return "Chemin invalide."
    return None


def _exec(ws: "Workspace", tool: str, a: dict) -> str:
    try:
        if tool == "list":
            return ws.t_list(str(a.get("dir", "")))
        if tool == "read":
            return ws.t_read(str(a.get("path", "")), a.get("start"), a.get("end"))
        if tool == "search":
            return ws.t_search(str(a.get("query", "")))
        if tool == "edit":
            return ws.t_edit(str(a.get("path", "")), str(a.get("old", "")), str(a.get("new", "")))
        if tool == "write":
            return ws.t_write(str(a.get("path", "")), str(a.get("content", "")))
        return f"Outil inconnu : {tool}. Outils : list, read, search, edit, write, done."
    except (ValueError, OSError) as e:
        return f"Erreur : {e}"


def _wrap(tool: str, res: str) -> str:
    """Les résultats qui contiennent du contenu du projet sont encadrés comme données non fiables."""
    from .security import untrusted
    return untrusted(res, f"résultat de {tool}") if tool in ("read", "search", "list", "test") else res


def _is_ok(res: str) -> bool:
    return not res.startswith(("Échec (code","Erreur", "Fichier introuvable", "« old »", "Lis d'abord", "Outil inconnu"))


def _show(a: dict) -> dict:
    return {k: (v if k not in ("content", "new", "old") else f"{len(str(v).splitlines())} ligne(s)") for k, v in a.items() if k != "tool"}
