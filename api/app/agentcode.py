"""Mode agent (Code) : Atom enchaîne seul lire → chercher → modifier, puis te présente l'ensemble à valider.

Garde-fous :
- l'agent travaille sur une copie en mémoire : rien n'est écrit sur le disque pendant qu'il travaille ;
- à la fin, tu vois un diff par fichier et tu choisis ce que tu appliques (clones Git uniquement ; sinon patch) ;
- il ne peut ni exécuter de commande, ni sortir du projet, ni toucher à .git ;
- nombre d'étapes limité ; tu peux l'arrêter à tout moment ;
- le code n'est envoyé à une API distante que si tu as autorisé « bibliothèque et fichiers » et seulement
  aux fournisseurs marqués « private » ; sinon l'agent tourne en local.

Protocole (portable, sans « function calling ») : à chaque tour, le modèle écrit une courte réflexion puis
UNE action dans un bloc ```action {json}```. Atom exécute l'action et lui renvoie le résultat.
"""

from __future__ import annotations

import difflib
import json
import re
import secrets
import time
from typing import AsyncIterator

from . import db, hybrid, library, llm, providers
from .config import DEFAULT_MODEL, PROVIDER

MAX_STEPS = 25
READ_LINES = 400
_runs: dict[str, dict] = {}

SYSTEM = """Tu es l'agent de code d'Atom. Tu travailles sur le projet « {name} » pour réaliser la tâche de l'utilisateur.
Tu ne vois le projet qu'à travers des outils. Rien n'est écrit sur le disque : tes modifications seront montrées à
l'utilisateur, qui décidera de les appliquer.

Outils (une seule action par réponse) :
- {{"tool": "list", "dir": "chemin/relatif"}} : fichiers d'un dossier ("" = racine ; chemins relatifs, sans « ./ »)
- {{"tool": "read", "path": "fichier", "start": 1, "end": 400}} : lire des lignes (numérotées)
- {{"tool": "search", "query": "texte"}} : chercher un texte exact dans tout le projet
- {{"tool": "edit", "path": "fichier", "old": "texte exact existant", "new": "remplacement"}} : remplacer un passage.
  « old » doit apparaître UNE seule fois dans le fichier, copié à l'identique (espaces et indentation compris).
- {{"tool": "write", "path": "fichier", "content": "contenu complet"}} : créer un fichier (ou le réécrire s'il est court)
- {{"tool": "done", "summary": "ce que tu as changé et pourquoi, et ce que l'utilisateur doit vérifier"}}

Si la tâche est une QUESTION (expliquer, décrire, trouver, analyser) : explore et lis les fichiers utiles sans rien
modifier, puis réponds en détail dans « summary » de l'action done (rôle du projet, architecture, fichiers clés,
fonctionnement, points d'attention), en Markdown.

Méthode :
1. Au premier tour, écris un PLAN court (3 à 6 étapes numérotées), puis ta première action.
2. Lis avant de modifier : ne modifie jamais un passage que tu n'as pas lu.
3. Fais des modifications minimales et ciblées ; garde le style du projet.
4. Si la tâche est ambiguë ou impossible, termine avec « done » et explique pourquoi.
5. Termine toujours par « done ».

Format de chaque réponse : une ou deux phrases de réflexion, puis exactement :
```action
{{ ...json... }}
```

Fichiers du projet (extrait) :
{files}

Arborescence (dossiers) :
{tree}
"""


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


def _parse(reply: str) -> tuple[str, dict | None]:
    m = re.search(r"```(?:action|json)?\s*\n(\{[\s\S]*?\})\s*```", reply)
    raw = m.group(1) if m else None
    if raw is None:
        m2 = re.search(r"\{[\s\S]*\"tool\"[\s\S]*\}", reply)
        raw = m2.group(0) if m2 else None
    thought = reply[: m.start()].strip() if m else reply.strip()
    thought = re.sub(r"^\[[a-z_]+\]\s*", "", thought)
    if raw is None:
        return thought, None
    try:
        return thought, json.loads(raw)
    except ValueError:
        try:   # JSON avec retours à la ligne bruts dans les chaînes : on tente de les échapper
            return thought, json.loads(re.sub(r'(?<=[^\\])\n', "\\n", raw))
        except ValueError:
            return thought, None


def engine_for(engine: str) -> tuple[str, str]:
    """(moteur, explication). Le code ne sort que si tu l'as autorisé, et seulement vers un fournisseur « private »."""
    s = hybrid.settings()
    if engine == "local":
        return "local", "modèle local (aucune donnée ne sort)"
    if not hybrid.configured():
        return "local", "aucune API distante configurée : agent en local (plus lent et moins fiable)"
    if not s["allow_docs"]:
        return "local", "envoi du code non autorisé (Réglages → Connexions → « Ma bibliothèque et mes fichiers ») : agent en local"
    chain = providers.chain(s["provider"] or None, sensitive=True)
    if not chain:
        return "local", "aucun fournisseur autorisé à recevoir du code (ou quotas atteints) : agent en local"
    return "remote", f"{chain[0].name} · {providers.model_of(chain[0])}"


async def _ask(messages: list[dict], engine: str, used: dict) -> str:
    if engine == "remote":
        order = providers.chain(hybrid.settings()["provider"] or None, sensitive=True)
        try:
            return "".join([t async for t in providers.stream_chain(order, messages, used, max_tokens=4096)])
        except providers.Unavailable as e:
            used["fallback"] = str(e)
    if PROVIDER == "mock":
        return _mock(messages)
    return "".join([t async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, messages)])


def _mock(messages: list[dict]) -> str:
    """Agent de test : lit le premier fichier, ajoute un commentaire, termine."""
    turns = sum(1 for m in messages if m["role"] == "assistant")
    if turns == 0:
        return 'Plan :\n1. Lister\n2. Lire\n3. Modifier\n```action\n{"tool": "list", "dir": ""}\n```'
    last = messages[-1]["content"]
    if turns == 1:
        first = next((l for l in last.split("\n") if l and not l.endswith("/") and not l.startswith("Résultat")), "")
        return f'Je lis le fichier.\n```action\n{{"tool": "read", "path": "{first.strip()}"}}\n```'
    if turns == 2:
        path = re.search(r"Résultat de read :\n(\S+) \(lignes", last)
        line = re.search(r"\s+1\| (.*)", last)
        return ('J\'ajoute un commentaire.\n```action\n' + json.dumps({"tool": "edit", "path": path.group(1) if path else "",
                "old": line.group(1) if line else "", "new": "# modifié par l'agent\n" + (line.group(1) if line else "")}) + "\n```")
    return '```action\n{"tool": "done", "summary": "Commentaire ajouté en tête du fichier."}\n```'


def _trim(messages: list[dict]) -> None:
    """Garde le contexte court : les anciens résultats d'outils sont résumés."""
    results = [i for i, m in enumerate(messages) if m["role"] == "user" and m["content"].startswith("Résultat de ")]
    for i in results[:-6]:
        c = messages[i]["content"]
        if len(c) > 400:
            messages[i]["content"] = c[:300] + "\n… (ancien résultat raccourci)"


async def run(cid: int, task: str, engine: str = "remote") -> AsyncIterator[dict]:
    ws = Workspace(cid)
    eng, why = engine_for(engine)
    rid = secrets.token_hex(8)
    yield dict(type="start", id=rid, engine=eng, info=why, writable=_writable(ws.col))
    listing = ws.all_paths()
    files = "\n".join(listing[:150]) + (f"\n… ({len(listing)} fichiers au total)" if len(listing) > 150 else "")
    messages = [{"role": "system", "content": SYSTEM.format(name=ws.col["name"], tree=library.tree(cid, 80), files=files or "(aucun)")},
                {"role": "user", "content": f"Tâche : {task.strip()}"}]
    summary, bad = "", 0
    for step in range(1, MAX_STEPS + 1):
        used: dict = {}
        yield dict(type="thinking", step=step)
        try:
            reply = await _ask(messages, eng, used)
        except Exception as e:  # noqa: BLE001
            yield dict(type="error", message=f"Le modèle n'a pas répondu : {e}")
            break
        if used.get("fallback"):
            eng = "local"
            yield dict(type="info", message=f"API indisponible ({used['fallback'][:150]}) : l'agent continue en local.")
        elif used.get("name"):
            yield dict(type="engine", name=f"{used['name']} · {used.get('model', '')}")
        thought, action = _parse(reply)
        messages.append({"role": "assistant", "content": reply})
        if not action or "tool" not in action:
            bad += 1
            yield dict(type="thought", step=step, text=thought or reply[:500])
            if bad >= 3:
                yield dict(type="error", message="L'agent ne respecte pas le format d'action : arrêt.")
                break
            messages.append({"role": "user", "content": "Résultat de format : réponse invalide. Termine par UNE action dans un bloc ```action {json}```."})
            continue
        bad = 0
        tool = str(action.get("tool"))
        yield dict(type="action", step=step, thought=thought, tool=tool,
                   args={k: (v if k not in ("content", "new", "old") else f"{len(str(v).splitlines())} ligne(s)")
                         for k, v in action.items() if k != "tool"})
        if tool == "done":
            summary = str(action.get("summary", ""))
            break
        try:
            if tool == "list":
                res = ws.t_list(str(action.get("dir", "")))
            elif tool == "read":
                res = ws.t_read(str(action.get("path", "")), action.get("start"), action.get("end"))
            elif tool == "search":
                res = ws.t_search(str(action.get("query", "")))
            elif tool == "edit":
                res = ws.t_edit(str(action.get("path", "")), str(action.get("old", "")), str(action.get("new", "")))
            elif tool == "write":
                res = ws.t_write(str(action.get("path", "")), str(action.get("content", "")))
            else:
                res = f"Outil inconnu : {tool}. Outils : list, read, search, edit, write, done."
        except (ValueError, OSError) as e:
            res = f"Erreur : {e}"
        ok = not res.startswith(("Erreur", "Fichier introuvable", "« old »", "Lis d'abord", "Outil inconnu"))
        yield dict(type="result", step=step, tool=tool, ok=ok, text=res[:1500])
        messages.append({"role": "user", "content": f"Résultat de {tool} :\n{res}"})
        _trim(messages)
    else:
        yield dict(type="info", message=f"Limite de {MAX_STEPS} étapes atteinte : voici ce qui a été fait.")
    files = ws.diffs()
    _runs[rid] = {"cid": cid, "files": {f["path"]: (ws.original.get(f["path"]), ws.changes[f["path"]]) for f in files},
                  "at": time.time()}
    for k in [k for k, v in _runs.items() if time.time() - v["at"] > 3 * 3600]:
        _runs.pop(k, None)
    yield dict(type="done", id=rid, summary=summary, files=files)


def _writable(col: dict) -> bool:
    from .codeedit import writable
    return writable(col)


def apply(rid: str, paths: list[str]) -> dict:
    r = _runs.get(rid)
    if not r:
        raise KeyError("Résultat expiré : relance l'agent.")
    col = library.get_collection(r["cid"])
    if not col or not _writable(col):
        raise PermissionError("Projet en lecture seule (dossier serveur) : télécharge le patch.")
    root = library._code_root(col).resolve()
    done, conflicts = [], []
    for rel in paths:
        if rel not in r["files"]:
            continue
        old, new = r["files"][rel]
        p = (root / rel).resolve()
        if not str(p).startswith(str(root) + "/"):
            continue
        cur = p.read_text("utf-8", "ignore") if p.is_file() else None
        if cur != old:
            conflicts.append(rel)
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new, "utf-8")
        done.append(rel)
        r["files"].pop(rel)
    return {"applied": done, "conflicts": conflicts}
