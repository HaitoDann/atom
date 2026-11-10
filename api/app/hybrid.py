"""Mode hybride : le modèle local par défaut, un modèle distant quand ça vaut le coup.

- Plusieurs fournisseurs possibles (voir providers.py) : le principal d'abord, puis relais automatique.

- Moteurs : « local » (Ollama), « mistral » (API compatible OpenAI), « auto » (Atom choisit).
- En auto, Mistral sert pour les demandes longues ou complexes, et en secours si le local échoue.
- Confidentialité : par défaut, ni la mémoire, ni la bibliothèque, ni les fichiers joints ne partent.
  Si une demande en a besoin et que l'envoi n'est pas autorisé, Atom reste en local.
- Un quota quotidien protège l'offre gratuite ; une fois atteint, Atom repasse en local.
- La mémorisation, les embeddings et l'indexation restent toujours en local.
"""

from __future__ import annotations

import json
import os
import logging
import re
from typing import AsyncIterator

from . import db, providers
from .config import MAX_TOKENS_LONG, REMOTE_DAILY_LIMIT, REMOTE_MODEL, REMOTE_NAME

log = logging.getLogger("atom.hybrid")
last_stats: dict = {}
last_used: dict = {}   # {id, name, model, skipped} du dernier appel distant

DEFAULTS = {
    "mode": "local",          # moteur par défaut : local | auto | mistral
    "allow_memory": False,    # envoyer les souvenirs à Mistral
    "allow_docs": False,      # envoyer les extraits de la bibliothèque et les fichiers joints
    "allow_web": True,        # envoyer les résultats de recherche web (déjà publics)
    "model": "",              # (ancien) modèle du fournisseur principal — désormais réglé par fournisseur
    "provider": "",           # fournisseur principal ; vide = le premier configuré
    "orchestrate": "suggest", # tâche difficile dans la discussion : auto (orchestration directe) | suggest | off
    "auto_replace": True,     # modèle disparu chez un fournisseur : en choisir un autre automatiquement
}

COMPLEX = re.compile(
    r"\b(analyse|analyser|explique en détail|en détail|approfondi|compare|comparer|comparatif|rédige|rédiger|"
    r"résume ce|traduis|traduire|plan|stratégie|architecture|optimise|refactor|débogue|debug|démontre|"
    r"pourquoi exactement|avantages et inconvénients|étape par étape)\b",
    re.I,
)


def configured() -> bool:
    return any(p.configured for p in providers.ALL)


def settings() -> dict:
    raw = db.kv_get("hybrid")
    s = dict(DEFAULTS)
    if raw:
        try:
            s.update({k: v for k, v in json.loads(raw).items() if k in DEFAULTS})
        except ValueError:
            pass
    return s


def save_settings(new: dict) -> dict:
    s = settings()
    if new.get("model") is not None:   # le modèle se règle par fournisseur
        p = primary()
        if p:
            providers.set_model(p.id, new.pop("model"))
    s.update({k: v for k, v in new.items() if k in DEFAULTS})
    if s["mode"] not in ("local", "auto", "mistral"):
        s["mode"] = "local"
    if s["orchestrate"] not in ("auto", "suggest", "off"):
        s["orchestrate"] = "suggest"
    if s["provider"] and not providers.get(s["provider"]):
        s["provider"] = ""
    db.kv_set("hybrid", json.dumps(s))
    return s


def primary() -> providers.Provider | None:
    """Le fournisseur choisi pour les réponses approfondies (sinon le premier configuré)."""
    pid = settings()["provider"]
    return providers.get(pid) or next((p for p in providers.ALL if p.configured), None)


def name() -> str:
    """Nom à afficher : le fournisseur qui vient de répondre, sinon le principal."""
    p = primary()
    return p.name if p else REMOTE_NAME


def model() -> str:
    p = primary()
    return providers.model_of(p) if p else REMOTE_MODEL


def used_today() -> int:
    return sum(providers.used_today(p.id) for p in providers.ALL)


def quota_left() -> int:
    return sum(providers.quota_left(p.id) for p in providers.ALL if p.configured)


def status() -> dict:
    p = primary()
    return {**settings(), "configured": configured(), "name": name(), "model": model(), "provider": p.id if p else "",
            "model_setting": providers.model_of(p) if p else "", "used_today": providers.used_today(p.id) if p else 0,
            "limit": p.limit if p else REMOTE_DAILY_LIMIT, "providers": [providers.describe(x) for x in providers.ALL],
            "skipped": providers.SKIPPED, "providers_env": os.getenv("ATOM_PROVIDERS", "") or ",".join(x.id for x in providers.ALL[1:])}


def decide(engine: str, message: str, needs_memory: bool, needs_docs: bool) -> tuple[str, str]:
    """Renvoie (moteur, raison). Moteur : « local » ou « mistral » (= distant, quel que soit le fournisseur)."""
    s = settings()
    engine = s["mode"] if engine in ("", "default") else engine
    if engine == "local":
        return "local", ""
    if not configured():
        return "local", "Aucun fournisseur distant configuré (clé API absente)."
    sensitive = (needs_memory and s["allow_memory"]) or (needs_docs and s["allow_docs"])
    if not providers.chain(s["provider"] or None, sensitive):
        return "local", "Quotas distants du jour atteints (ou fournisseurs en pause) : réponse en local."
    if needs_docs and not s["allow_docs"]:
        return "local", "Cette demande utilise ta bibliothèque ou un fichier, dont l'envoi n'est pas autorisé."
    if engine == "mistral":
        return "mistral", "demandé"
    m = message.strip()
    kind = classify(m)
    if kind == "code":
        return "mistral", "demande de code : modèle distant fort en code"
    if kind == "complexe":
        return "mistral", "demande longue ou complexe"
    return "local", ""


def orchestration_plan(message: str, engine: str = "default", has_files: bool = False) -> dict:
    """Faut-il passer cette demande de la discussion à l'orchestration vérifiée ?
    Conclusions du banc d'essai : un bon modèle distant suffit aux demandes simples et moyennes (rapide) ;
    l'orchestration rattrape surtout le petit modèle local, et sert pour les tâches en plusieurs étapes.
    Jamais avec des fichiers joints ni quand un modèle distant est imposé (le plus fort répond déjà)."""
    from . import orchestrator
    s = settings()
    level = orchestrator.difficulty(message or "")
    mode = s["orchestrate"]
    out = {"difficulty": level, "mode": mode, "orchestrate": False, "suggest": False, "reason": ""}
    if mode == "off" or has_files or engine == "mistral" or level != "difficile":
        return out
    out["reason"] = ("tâche en plusieurs étapes : découpage, petits modèles vérifiés (calculs exécutés, sources, "
                     "juge d'une autre famille), puis assemblage")
    out["orchestrate" if mode == "auto" else "suggest"] = True
    return out


async def list_models(pid: str | None = None) -> list[str]:
    p = providers.get(pid) if pid else primary()
    if not p or not p.configured:
        return []
    return await providers.list_models(p)


CODE = re.compile(r"```|\b(code|fonction|classe|bug|erreur de compilation|stack ?trace|regex|sql|python|javascript|"
                  r"typescript|golang|rust|bash|script|api|refactor|débogue|debug|compile|test unitaire)\b", re.I)


def classify(message: str) -> str:
    """Nature de la demande : « code », « complexe » ou « simple » (sert à choisir le fournisseur)."""
    m = message or ""
    if CODE.search(m):
        return "code"
    if len(m) > 600 or COMPLEX.search(m) or m.count("\n") > 8:
        return "complexe"
    return "simple"


async def stream(messages: list[dict], model_name: str | None = None, sensitive: bool = False, task: str | None = None) -> AsyncIterator[str]:
    """Flux depuis le fournisseur principal, avec relais vers les autres s'il est indisponible.
    sensitive=True : la demande contient souvenirs/documents → seulement les fournisseurs « private »."""
    p = primary()
    if task is None:
        task = classify(next((m["content"] for m in reversed(messages) if m["role"] == "user"), ""))
    est = providers.estimate_tokens(messages)
    if task != "code" and est > 6000:
        task = "long"
    rows = providers.plan(p.id if p else None, sensitive, task=task, est_tokens=est)
    order = [r["provider"] for r in rows]
    used: dict = {}
    try:
        long = task in ("code", "long", "complexe")
        async for t in providers.stream_complete(order, messages, used, model_name, max_tokens=MAX_TOKENS_LONG if long else None,
                                                 task=task, reason=providers.explain(rows)):
            yield t
    finally:
        last_used.clear()
        last_used.update({k: v for k, v in used.items() if k != "stats"})
        last_stats.clear()
        last_stats.update(used.get("stats", {}))
        if used.get("id"):
            last_stats["provider"] = "mistral"
