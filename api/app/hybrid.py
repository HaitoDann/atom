"""Mode hybride : le modèle local par défaut, Mistral quand ça vaut le coup.

- Moteurs : « local » (Ollama), « mistral » (API compatible OpenAI), « auto » (Atom choisit).
- En auto, Mistral sert pour les demandes longues ou complexes, et en secours si le local échoue.
- Confidentialité : par défaut, ni la mémoire, ni la bibliothèque, ni les fichiers joints ne partent.
  Si une demande en a besoin et que l'envoi n'est pas autorisé, Atom reste en local.
- Un quota quotidien protège l'offre gratuite ; une fois atteint, Atom repasse en local.
- La mémorisation, les embeddings et l'indexation restent toujours en local.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import AsyncIterator

import httpx

from . import db
from .config import MAX_TOKENS, PROVIDER, REMOTE_API_KEY, REMOTE_DAILY_LIMIT, REMOTE_MODEL, REMOTE_NAME, REMOTE_URL

log = logging.getLogger("atom.hybrid")
last_stats: dict = {}

DEFAULTS = {
    "mode": "local",          # moteur par défaut : local | auto | mistral
    "allow_memory": False,    # envoyer les souvenirs à Mistral
    "allow_docs": False,      # envoyer les extraits de la bibliothèque et les fichiers joints
    "allow_web": True,        # envoyer les résultats de recherche web (déjà publics)
    "model": "",              # vide = ATOM_REMOTE_MODEL
}

COMPLEX = re.compile(
    r"\b(analyse|analyser|explique en détail|en détail|approfondi|compare|comparer|comparatif|rédige|rédiger|"
    r"résume ce|traduis|traduire|plan|stratégie|architecture|optimise|refactor|débogue|debug|démontre|"
    r"pourquoi exactement|avantages et inconvénients|étape par étape)\b",
    re.I,
)


def configured() -> bool:
    return PROVIDER == "mock" or bool(REMOTE_API_KEY)


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
    s.update({k: v for k, v in new.items() if k in DEFAULTS})
    if s["mode"] not in ("local", "auto", "mistral"):
        s["mode"] = "local"
    db.kv_set("hybrid", json.dumps(s))
    return s


def model() -> str:
    return settings()["model"] or REMOTE_MODEL


def _today_key() -> str:
    return "hybrid:used:" + datetime.now().strftime("%Y-%m-%d")


def used_today() -> int:
    return int(db.kv_get(_today_key(), "0") or 0)


def _count() -> None:
    db.kv_set(_today_key(), str(used_today() + 1))


def quota_left() -> int:
    return max(0, REMOTE_DAILY_LIMIT - used_today())


def status() -> dict:
    return {**settings(), "configured": configured(), "name": REMOTE_NAME, "model": model(),
            "model_setting": settings()["model"], "used_today": used_today(), "limit": REMOTE_DAILY_LIMIT}


def decide(engine: str, message: str, needs_memory: bool, needs_docs: bool) -> tuple[str, str]:
    """Renvoie (moteur, raison). Moteur : « local » ou « mistral »."""
    s = settings()
    engine = s["mode"] if engine in ("", "default") else engine
    if engine == "local":
        return "local", ""
    if not configured():
        return "local", "Mistral n'est pas configuré (clé API absente)."
    if quota_left() <= 0:
        return "local", "Quota Mistral du jour atteint : réponse en local."
    if needs_docs and not s["allow_docs"]:
        return "local", "Cette demande utilise ta bibliothèque ou un fichier, dont l'envoi à Mistral n'est pas autorisé."
    if engine == "mistral":
        return "mistral", "demandé"
    # auto : Mistral pour ce qui dépasse le petit modèle local
    m = message.strip()
    if len(m) > 600 or COMPLEX.search(m) or m.count("\n") > 8:
        return "mistral", "demande longue ou complexe"
    return "local", ""


async def list_models() -> list[str]:
    """Modèles proposés par le fournisseur (endpoint /models, format OpenAI)."""
    if PROVIDER == "mock":
        return ["mistral-small-latest", "mistral-large-latest"]
    if not REMOTE_API_KEY:
        return []
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{REMOTE_URL}/models", headers={"Authorization": f"Bearer {REMOTE_API_KEY}"})
    if r.status_code != 200:
        raise RuntimeError(f"{REMOTE_NAME} a répondu {r.status_code}")
    data = r.json().get("data", [])
    skip = ("whisper", "tts", "embed", "guard", "moderation", "ocr", "transcri", "speech", "audio", "image", "vision-preview")
    ids = [m.get("id", "") for m in data if m.get("id") and not any(x in m.get("id", "").lower() for x in skip)
           and m.get("active", True) is not False]
    return sorted(set(ids))


async def stream(messages: list[dict], model_name: str | None = None) -> AsyncIterator[str]:
    """Flux de texte depuis l'API (format OpenAI : /chat/completions en SSE)."""
    if PROVIDER == "mock":
        reply = "[curious] (Mistral, mode test) Voici une réponse plus approfondie, venue de l'extérieur."
        for w in re.findall(r"\S+\s*", reply):
            yield w
        last_stats.clear()
        last_stats.update(tokens=12, tok_s=40.0, provider="mistral")
        _count()
        return
    payload = {"model": model_name or model(), "messages": messages, "stream": True,
               "temperature": 0.6, "max_tokens": MAX_TOKENS}
    headers = {"Authorization": f"Bearer {REMOTE_API_KEY}", "Accept": "text/event-stream"}
    t0, first, n = time.time(), None, 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(15, read=120)) as client:
        async with client.stream("POST", f"{REMOTE_URL}/chat/completions", json=payload, headers=headers) as r:
            if r.status_code != 200:
                body = (await r.aread()).decode(errors="replace")[:300]
                if r.status_code == 401:
                    raise RuntimeError(f"clé API {REMOTE_NAME} refusée, vérifie ATOM_REMOTE_API_KEY")
                if r.status_code == 429:
                    raise RuntimeError(f"limite de l'offre {REMOTE_NAME} atteinte pour le moment")
                if r.status_code == 404 and "model" in body.lower():
                    raise RuntimeError(f"le modèle « {payload['model']} » n'existe pas chez {REMOTE_NAME} : "
                                       "choisis-en un dans Réglages → Hybride")
                raise RuntimeError(f"{REMOTE_NAME} a répondu {r.status_code} : {body}")
            _count()
            usage = {}
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except ValueError:
                    continue
                usage = chunk.get("usage") or usage
                for ch in chunk.get("choices", []):
                    text = (ch.get("delta") or {}).get("content") or ""
                    if text:
                        first = first or time.time()
                        n += 1
                        yield text
    dur = time.time() - (first or t0)
    toks = usage.get("completion_tokens", n)
    last_stats.clear()
    last_stats.update(tokens=toks, tok_s=round(toks / dur, 1) if dur > 0 else None, provider="mistral",
                      prompt_tokens=usage.get("prompt_tokens"), total_s=round(time.time() - t0, 2))
