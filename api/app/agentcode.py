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

import asyncio
import difflib
import json
import re
import secrets
import time
from typing import AsyncIterator

from . import db, hybrid, library, llm, providers, sandbox
from .config import DEFAULT_MODEL, PROVIDER

MAX_STEPS = 25
READ_LINES = 250

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
- {{"tool": "done", "summary": "ce que tu as changé et pourquoi, et ce que l'utilisateur doit vérifier"}}{test_tool}

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

{test_note}Fichiers du projet (extrait) :
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
        self.stopped = lambda: False

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


def tools() -> list[dict]:
    return TOOLS + ([TEST_TOOL] if sandbox.enabled() else [])


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


def _is_ok(res: str) -> bool:
    return not res.startswith(("Échec (code","Erreur", "Fichier introuvable", "« old »", "Lis d'abord", "Outil inconnu"))


def _show(a: dict) -> dict:
    return {k: (v if k not in ("content", "new", "old") else f"{len(str(v).splitlines())} ligne(s)") for k, v in a.items() if k != "tool"}


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


def _est(messages: list[dict]) -> int:
    """Estimation grossière des tokens (≈ 3,2 caractères par token pour du code et du français)."""
    return int(sum(len(json.dumps(m, ensure_ascii=False)) for m in messages) / 3.2) + 600   # + définitions d'outils


def _fit(messages: list[dict], budget: int) -> list[dict]:
    """Copie des messages qui tient dans le budget : les anciens résultats sont raccourcis d'abord."""
    out = [dict(m) for m in messages]
    idx = [i for i, m in enumerate(out) if m["role"] == "tool" or (m["role"] == "user" and i > 1)]
    for i in idx[:-1]:
        if _est(out) <= budget:
            return out
        c = str(out[i].get("content") or "")
        if len(c) > 240:
            out[i]["content"] = c[:200] + "\n… (ancien résultat raccourci pour tenir dans la limite)"
    if idx and _est(out) > budget:   # le dernier résultat lui-même est trop long : on garde le début
        i = idx[-1]
        c = str(out[i].get("content") or "")
        keep = max(800, len(c) - int((_est(out) - budget) * 3.2) - 200)
        out[i]["content"] = c[:keep] + "\n… (tronqué pour tenir dans la limite : relis la suite avec start=…)"
    return out


def _trim(messages: list[dict]) -> None:
    """Garde le contexte court : les anciens résultats d'outils sont résumés."""
    results = [i for i, m in enumerate(messages) if m["role"] == "tool"
               or (m["role"] == "user" and str(m.get("content", "")).startswith("Résultat de "))]
    for i in results[:-6]:
        c = messages[i]["content"]
        if len(c) > 400:
            messages[i]["content"] = c[:300] + "\n… (ancien résultat raccourci)"


async def _run_native(ws: "Workspace", system: str, task: str, state: dict) -> AsyncIterator[dict]:
    """Boucle avec outils natifs des API (Groq, Gemini, GitHub Models…)."""
    messages = [{"role": "system", "content": system + NATIVE_NOTE}, {"role": "user", "content": f"Tâche : {task.strip()}"}]
    order = providers.chain(hybrid.settings()["provider"] or None, sensitive=True)
    announced, nudges = None, 0
    for step in range(1, MAX_STEPS + 1):
        state["step"] = step
        if ws.stopped():
            state["finished"] = True
            yield dict(type="info", message="Arrêté à ta demande.")
            return
        yield dict(type="thinking", step=step)
        msg, errors, waits = None, [], []
        for attempt in range(4):
            msg, errors, waits = None, [], []
            for p in list(order):
                try:
                    bud = providers.budget(p)
                    out_tok = min(2048, max(600, int(bud * 0.25)))
                    try:
                        msg = await providers.chat_tools(p, _fit(messages, bud - out_tok), tools(), out_tok)
                    except providers.TooLarge:
                        small = int(bud * 0.6)   # estimation trop optimiste : on réessaie nettement plus court
                        msg = await providers.chat_tools(p, _fit(messages, small - 600), tools(), 600)
                    if announced != p.id:
                        announced = p.id
                        yield dict(type="engine", name=f"{p.name} · {providers.model_of(p)}")
                    order = [p] + [x for x in order if x is not p]   # on garde le fournisseur qui marche
                    break
                except providers.RateLimited as e:
                    errors.append(str(e))
                    if e.wait < 120:
                        waits.append(e.wait)
                    else:
                        order = [x for x in order if x is not p]   # limite du jour : on l'écarte
                except providers.Unavailable as e:
                    errors.append(str(e))
                    order = [x for x in order if x is not p]
            if msg is not None or not waits:
                break
            # Tous limités pour la minute : mieux vaut patienter que basculer sur le modèle local.
            pause = min(65, max(3, min(waits) + 1))
            yield dict(type="info", message=f"Limite par minute atteinte ({errors[0]}) : pause de {int(pause)} s puis reprise.")
            await asyncio.sleep(pause)
        if msg is None:
            state["fallback"] = " ; ".join(errors) or "aucun fournisseur disponible"
            return
        content = re.sub(r"<think>[\s\S]*?</think>", "", msg.get("content") or "").strip()
        calls = msg.get("tool_calls") or []
        if not calls:
            if content and (nudges >= 1 or step > 1):
                # réponse directe sans outil : on la prend comme conclusion
                yield dict(type="action", step=step, thought="", tool="done", args={})
                state.update(summary=content, finished=True)
                return
            nudges += 1
            if content:
                yield dict(type="thought", step=step, text=content[:600])
            messages.append({"role": "assistant", "content": content or "…"})
            messages.append({"role": "user", "content": "Utilise les outils (list, read, search…) pour explorer le projet, puis termine par done."})
            continue
        messages.append({"role": "assistant", "content": content or None, "tool_calls": calls})
        for i, c in enumerate(calls):
            fn = (c.get("function") or {})
            tool = str(fn.get("name", ""))
            try:
                args = json.loads(fn.get("arguments") or "{}") if isinstance(fn.get("arguments"), str) else (fn.get("arguments") or {})
            except ValueError:
                args = {}
            yield dict(type="action", step=step, thought=content if i == 0 else "", tool=tool, args=_show(args))
            if tool == "done":
                state.update(summary=str(args.get("summary", content)), finished=True)
                return
            if tool == "test" and sandbox.enabled():
                yield dict(type="info", message="Tests dans le bac à sable (sans réseau)…")
                res = await sandbox.run_text(ws.cid, args.get("command"), ws.changes)
            else:
                res = _exec(ws, tool, args)
            yield dict(type="result", step=step, tool=tool, ok=_is_ok(res), text=res[:1500])
            messages.append({"role": "tool", "tool_call_id": c.get("id") or f"call_{step}_{i}", "content": res})
        _trim(messages)
    state["finished"] = True
    yield dict(type="info", message=f"Limite de {MAX_STEPS} étapes atteinte : voici ce qui a été fait.")


async def _run_text(ws: "Workspace", system: str, task: str, state: dict) -> AsyncIterator[dict]:
    """Boucle au format texte (```action```) : modèle local, ou API sans outils natifs."""
    note = ""
    if ws.changes:
        note = "\n\nModifications déjà préparées : " + ", ".join(sorted(ws.changes)) + " (relis-les avant d'aller plus loin)."
    messages = [{"role": "system", "content": system}, {"role": "user", "content": f"Tâche : {task.strip()}{note}"}]
    bad = 0
    for step in range(state.get("step", 0) + 1, MAX_STEPS + 1):
        if ws.stopped():
            yield dict(type="info", message="Arrêté à ta demande.")
            return
        yield dict(type="thinking", step=step)
        try:
            if PROVIDER == "mock":
                reply = _mock(messages)
            else:
                reply = "".join([t async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, messages)])
        except Exception as e:  # noqa: BLE001
            yield dict(type="error", message=f"Le modèle n'a pas répondu : {e}")
            return
        thought, action = _parse(reply)
        messages.append({"role": "assistant", "content": reply})
        if not action or "tool" not in action:
            bad += 1
            yield dict(type="thought", step=step, text=thought or reply[:500])
            if bad >= 3:
                yield dict(type="error", message="L'agent ne respecte pas le format d'action : arrêt.")
                return
            messages.append({"role": "user", "content": "Résultat de format : réponse invalide. Termine par UNE action dans un bloc ```action {json}```."})
            continue
        bad = 0
        tool = str(action.get("tool"))
        yield dict(type="action", step=step, thought=thought, tool=tool, args=_show(action))
        if tool == "done":
            state["summary"] = str(action.get("summary", ""))
            return
        if tool == "test" and sandbox.enabled():
            yield dict(type="info", message="Tests dans le bac à sable (sans réseau)…")
            res = await sandbox.run_text(ws.cid, action.get("command"), ws.changes)
        else:
            res = _exec(ws, tool, action)
        yield dict(type="result", step=step, tool=tool, ok=_is_ok(res), text=res[:1500])
        messages.append({"role": "user", "content": f"Résultat de {tool} :\n{res}"})
        _trim(messages)
    yield dict(type="info", message=f"Limite de {MAX_STEPS} étapes atteinte : voici ce qui a été fait.")


async def run(cid: int, task: str, engine: str = "remote", rid: str | None = None,
              parent: dict | None = None) -> AsyncIterator[dict]:
    ws = Workspace(cid)
    rid = rid or secrets.token_hex(8)
    ws.stopped = lambda: rid in _stop
    if parent:   # « Poursuivre » : on repart des modifications déjà préparées (non appliquées)
        for path, (old, new) in (parent.get("files") or {}).items():
            ws.original[path], ws.changes[path] = old, new
            ws.read_ok.add(path)
        task = (f"Tâche précédente : {parent.get('task', '')}\nCe que tu avais conclu : {(parent.get('summary') or '')[:3000]}\n"
                + (f"Fichiers déjà modifiés (en attente de validation) : {', '.join(sorted(parent.get('files') or {}))}\n" if parent.get("files") else "")
                + f"\nNouvelle demande : {task}")
    eng, why = engine_for(engine)
    yield dict(type="start", id=rid, engine=eng, info=why, writable=_writable(ws.col))
    listing = ws.all_paths()
    files = "\n".join(listing[:150]) + (f"\n… ({len(listing)} fichiers au total)" if len(listing) > 150 else "")
    # Consignes du projet (comme Claude Code / Cursor) : lues automatiquement si présentes à la racine.
    rules = []
    for name in ("AGENTS.md", "CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md", "CONVENTIONS.md"):
        t = ws.text(name)
        if t:
            rules.append(f"--- {name} ---\n{t[:3000]}")
    sb = sandbox.enabled()
    system = SYSTEM.format(name=ws.col["name"], tree=library.tree(cid, 80), files=files or "(aucun)",
                           test_tool=TEST_TEXT if sb else "",
                           test_note=TEST_NOTE.format(cmd=sandbox.default_command(cid, listing + [p.name for p in ws.root.iterdir() if p.is_file()]) or "à préciser") if sb else "")
    learned = get_rules(cid)
    if learned:
        rules.append("--- règles retenues par l'utilisateur ---\n" + "\n".join(f"- {r}" for r in learned))
    if rules:
        system += "\n\nConsignes du projet (à respecter en priorité) :\n" + "\n\n".join(rules)[:6000]
    summary, finished = "", False
    step = 0
    if eng == "remote":
        state: dict = {}
        async for ev in _run_native(ws, system, task, state):
            yield ev
        step, summary, finished = state.get("step", 0), state.get("summary", ""), state.get("finished", False)
        if not finished and state.get("fallback"):
            eng = "local"
            yield dict(type="info", message=f"API indisponible ({state['fallback'][:180]}) : l'agent continue en local"
                                            + (" (les modifications déjà préparées sont conservées)." if ws.changes else "."))
    if eng == "local" and not finished:
        state = {"step": step}
        async for ev in _run_text(ws, system, task, state):
            yield ev
        summary = state.get("summary", "")
    files = ws.diffs()
    store = {f["path"]: (ws.original.get(f["path"]), ws.changes[f["path"]]) for f in files}
    yield dict(type="done", id=rid, summary=summary, files=files, _store=store)


# ---------------------------------------------------------------- tâches en arrière-plan (survivent à F5)

_stop: set[str] = set()
_live: dict[str, dict] = {}   # rid → {"events": [...], "task": asyncio.Task}


def init() -> None:
    with db.conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS agent_runs (
            id TEXT PRIMARY KEY, collection_id INTEGER NOT NULL, task TEXT NOT NULL, engine TEXT,
            status TEXT NOT NULL, summary TEXT, events TEXT, files TEXT, parent TEXT,
            created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
        # tâches interrompues par un redémarrage du serveur
        c.execute("UPDATE agent_runs SET status = 'interrupted' WHERE status = 'running'")


def _save(rid: str, **fields) -> None:
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with db.conn() as c:
        c.execute(f"UPDATE agent_runs SET {cols} WHERE id = ?", (*fields.values(), rid))


def get_run(rid: str) -> dict | None:
    with db.conn() as c:
        r = c.execute("SELECT * FROM agent_runs WHERE id = ?", (rid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    live = _live.get(rid)
    d["events"] = live["events"] if live else json.loads(d["events"] or "[]")
    d["files"] = json.loads(d["files"] or "{}")
    return d


def list_runs(cid: int, limit: int = 30) -> list[dict]:
    with db.conn() as c:
        rows = c.execute("SELECT id, task, status, summary, parent, created_at, updated_at, files FROM agent_runs "
                         "WHERE collection_id = ? ORDER BY created_at DESC LIMIT ?", (cid, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["files"] = len(json.loads(d["files"] or "{}"))
        d["summary"] = (d["summary"] or "")[:200]
        out.append(d)
    return out


def delete_run(rid: str) -> None:
    with db.conn() as c:
        c.execute("DELETE FROM agent_runs WHERE id = ?", (rid,))


def start(cid: int, task: str, engine: str, parent_id: str | None = None) -> str:
    import asyncio

    parent = get_run(parent_id) if parent_id else None
    rid = secrets.token_hex(8)
    now = time.time()
    with db.conn() as c:
        c.execute("INSERT INTO agent_runs (id, collection_id, task, engine, status, events, files, parent, created_at, updated_at) "
                  "VALUES (?, ?, ?, ?, 'running', '[]', '{}', ?, ?, ?)", (rid, cid, task.strip(), engine, parent_id, now, now))
    live = _live[rid] = {"events": []}

    async def job():
        status, summary, files = "done", "", {}
        last_save = time.time()
        try:
            async for ev in run(cid, task, engine, rid, parent):
                if ev["type"] == "done":
                    files = ev.pop("_store", {})
                    summary = ev.get("summary", "")
                if ev["type"] == "error":
                    status = "error"
                live["events"].append(ev)
                if time.time() - last_save > 3:
                    _save(rid, events=json.dumps(live["events"], ensure_ascii=False))
                    last_save = time.time()
        except Exception as e:  # noqa: BLE001
            status = "error"
            live["events"].append(dict(type="error", message=f"Agent interrompu : {e}"))
            live["events"].append(dict(type="done", id=rid, summary="", files=[]))
        if rid in _stop:
            status = "stopped"
            _stop.discard(rid)
        _save(rid, status=status, summary=summary, events=json.dumps(live["events"], ensure_ascii=False),
              files=json.dumps({k: list(v) for k, v in files.items()}, ensure_ascii=False))
        _live.pop(rid, None)

    live["task"] = asyncio.create_task(job())
    return rid


def stop(rid: str) -> None:
    if rid in _live:
        _stop.add(rid)


def _writable(col: dict) -> bool:
    from .codeedit import writable
    return writable(col)


def apply(rid: str, paths: list[str]) -> dict:
    r = get_run(rid)
    if not r or not r["files"]:
        raise KeyError("Rien à appliquer pour cette tâche.")
    col = library.get_collection(r["collection_id"])
    if not col or not _writable(col):
        raise PermissionError("Projet en lecture seule (dossier serveur) : télécharge le patch.")
    root = library._code_root(col).resolve()
    files = dict(r["files"])
    done, conflicts = [], []
    for rel in paths:
        if rel not in files:
            continue
        old, new = files[rel]
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
        files.pop(rel)
    _save(rid, files=json.dumps(files, ensure_ascii=False))
    # les diffs restants dans l'événement final, pour l'affichage après rechargement
    with db.conn() as c:
        row = c.execute("SELECT events FROM agent_runs WHERE id = ?", (rid,)).fetchone()
    evs = json.loads(row["events"] or "[]") if row else []
    for ev in evs:
        if ev.get("type") == "done":
            ev["files"] = [f for f in ev.get("files", []) if f["path"] in files]
            ev["applied"] = sorted(set(ev.get("applied", [])) | set(done))
    _save(rid, events=json.dumps(evs, ensure_ascii=False))
    return {"applied": done, "conflicts": conflicts, "collection_id": r["collection_id"]}


# ---------------------------------------------------------------- règles retenues par projet


def get_rules(cid: int) -> list[str]:
    try:
        return [r for r in json.loads(db.kv_get(f"agent:rules:{cid}") or "[]") if isinstance(r, str)]
    except ValueError:
        return []


def set_rules(cid: int, rules: list[str]) -> list[str]:
    clean = [r.strip()[:300] for r in rules if r and r.strip()][:40]
    db.kv_set(f"agent:rules:{cid}", json.dumps(clean, ensure_ascii=False))
    return clean
