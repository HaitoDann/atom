"""Fournisseurs d'IA distants (API compatibles OpenAI) : plusieurs à la fois, avec relais automatique.

Configuration dans .env :
- le fournisseur principal historique : ATOM_REMOTE_NAME / _URL / _MODEL / _API_KEY / _DAILY_LIMIT ;
- des fournisseurs en plus : ATOM_PROVIDERS=groq,cerebras,gemini puis, pour chacun,
  ATOM_<ID>_API_KEY (obligatoire) et au besoin _MODEL, _URL, _LIMIT, _FAMILY, _STRENGTH, _PRIVATE.
  Les fournisseurs connus (PRESETS) ont déjà leur adresse, un modèle par défaut et leur famille.

Chaque fournisseur a :
- un quota quotidien à lui ;
- une famille de modèles (llama, qwen, gemini…) : l'atelier fait relire par une autre famille ;
- une force (1 à 3) : l'arbitre n'est jamais le plus faible ;
- un drapeau « private » : s'il est faux, il ne reçoit jamais tes souvenirs, documents ni fichiers,
  même si le mode hybride l'autorise (ex. offres gratuites qui peuvent réutiliser les données).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator

import httpx

from . import db
from .config import MAX_TOKENS, PROVIDER, REMOTE_API_KEY, REMOTE_DAILY_LIMIT, REMOTE_MODEL, REMOTE_NAME, REMOTE_URL

log = logging.getLogger("atom.providers")

PRESETS = {
    "groq": dict(name="Groq", url="https://api.groq.com/openai/v1", model="llama-3.3-70b-versatile", family="llama", strength=3, private=True),
    "cerebras": dict(name="Cerebras", url="https://api.cerebras.ai/v1", model="qwen-3-235b-a22b-instruct-2507", family="qwen", strength=3, private=True),
    "gemini": dict(name="Gemini", url="https://generativelanguage.googleapis.com/v1beta/openai", model="gemini-2.5-flash", family="gemini", strength=3, private=False),
    "openrouter": dict(name="OpenRouter", url="https://openrouter.ai/api/v1", model="deepseek/deepseek-chat-v3-0324:free", family="deepseek", strength=2, private=False),
    "github": dict(name="GitHub Models", url="https://models.github.ai/inference", model="openai/gpt-4.1-mini", family="gpt", strength=3, private=True),
    "mistral": dict(name="Mistral", url="https://api.mistral.ai/v1", model="mistral-small-latest", family="mistral", strength=2, private=True),
}

FAMILIES = ["llama", "qwen", "gemini", "gemma", "mistral", "deepseek", "gpt", "claude", "phi", "kimi", "glm"]


def family_of(model: str, fallback: str = "autre") -> str:
    m = model.lower()
    for f in FAMILIES:
        if f in m or (f == "gpt" and re.search(r"\bo[134]\b|gpt-oss", m)):
            return f
    if "codestral" in m or "magistral" in m or "ministral" in m:
        return "mistral"
    return fallback


@dataclass
class Provider:
    id: str
    name: str
    url: str
    key: str
    model: str
    limit: int
    family: str
    strength: int
    private: bool
    extra: dict = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        return PROVIDER == "mock" or bool(self.key)


def _env(pid: str, k: str, default: str = "") -> str:
    return os.getenv(f"ATOM_{pid.upper()}_{k}", default)


def _bool(v: str, default: bool) -> bool:
    return default if v == "" else v.strip().lower() in ("1", "true", "oui", "yes")


SKIPPED: list[dict] = []   # fournisseurs listés dans ATOM_PROVIDERS mais inutilisables (avec la raison)


def _load() -> list[Provider]:
    out: list[Provider] = []
    if REMOTE_API_KEY or PROVIDER == "mock":
        pid = re.sub(r"[^a-z0-9]+", "", REMOTE_NAME.lower()) or "remote"
        pre = PRESETS.get(pid, {})
        out.append(Provider(pid, REMOTE_NAME, REMOTE_URL, REMOTE_API_KEY, REMOTE_MODEL, REMOTE_DAILY_LIMIT,
                            os.getenv("ATOM_REMOTE_FAMILY") or family_of(REMOTE_MODEL, pre.get("family", "autre")),
                            int(os.getenv("ATOM_REMOTE_STRENGTH") or pre.get("strength", 2)),
                            _bool(os.getenv("ATOM_REMOTE_PRIVATE", ""), pre.get("private", True))))
    for pid in [p.strip().lower() for p in os.getenv("ATOM_PROVIDERS", "").split(",") if p.strip()]:
        if any(p.id == pid for p in out):
            continue
        pre = PRESETS.get(pid, {})
        key = _env(pid, "API_KEY")
        if not key and PROVIDER != "mock":
            log.warning("fournisseur %s ignoré : ATOM_%s_API_KEY absent", pid, pid.upper())
            SKIPPED.append({"id": pid, "name": pre.get("name", pid.capitalize()), "reason": f"clé absente : ATOM_{pid.upper()}_API_KEY"})
            continue
        model = _env(pid, "MODEL", pre.get("model", ""))
        url = _env(pid, "URL", pre.get("url", "")).rstrip("/")
        if not url or not model:
            log.warning("fournisseur %s ignoré : adresse ou modèle manquant (ATOM_%s_URL / _MODEL)", pid, pid.upper())
            SKIPPED.append({"id": pid, "name": pid, "reason": f"fournisseur inconnu : ajoute ATOM_{pid.upper()}_URL et ATOM_{pid.upper()}_MODEL"})
            continue
        out.append(Provider(pid, _env(pid, "NAME", pre.get("name", pid.capitalize())), url, key, model,
                            int(_env(pid, "LIMIT", "200")),
                            _env(pid, "FAMILY") or family_of(model, pre.get("family", "autre")),
                            int(_env(pid, "STRENGTH", str(pre.get("strength", 2)))),
                            _bool(_env(pid, "PRIVATE"), pre.get("private", False))))
    return out


ALL: list[Provider] = _load()
LOCAL_STRENGTH = int(os.getenv("ATOM_LOCAL_STRENGTH", "1"))


def get(pid: str) -> Provider | None:
    return next((p for p in ALL if p.id == pid), None)


# ---------------------------------------------------------------- réglages par fournisseur (modèle choisi)


def model_of(p: Provider) -> str:
    return db.kv_get(f"prov:model:{p.id}") or p.model


def set_model(pid: str, model: str) -> None:
    db.kv_set(f"prov:model:{pid}", model.strip())


# ---------------------------------------------------------------- quotas


def _key(pid: str) -> str:
    return f"prov:used:{pid}:" + datetime.now().strftime("%Y-%m-%d")


def used_today(pid: str) -> int:
    v = db.kv_get(_key(pid))
    if v is None and ALL and ALL[0].id == pid:   # compatibilité : ancien compteur du mode hybride
        v = db.kv_get("hybrid:used:" + datetime.now().strftime("%Y-%m-%d"))
    return int(v or 0)


def count(pid: str) -> None:
    db.kv_set(_key(pid), str(used_today(pid) + 1))


def quota_left(pid: str) -> int:
    p = get(pid)
    return max(0, p.limit - used_today(pid)) if p else 0


# Fournisseur en pause après une erreur (limite atteinte, panne) : on ne le réessaie pas tout de suite.
_cooldown: dict[str, float] = {}


def available(p: Provider, sensitive: bool = False) -> bool:
    return (p.configured and quota_left(p.id) > 0 and _cooldown.get(p.id, 0) < time.time()
            and (p.private or not sensitive))


def chain(first: str | None = None, sensitive: bool = False, exclude: set[str] | None = None) -> list[Provider]:
    """Ordre d'essai : le fournisseur demandé, puis les autres du plus fort au plus faible."""
    exclude = exclude or set()
    pool = [p for p in ALL if p.id not in exclude and available(p, sensitive)]
    pool.sort(key=lambda p: (p.id != first, -p.strength))
    return pool


def describe(p: Provider) -> dict:
    return {"id": p.id, "name": p.name, "model": model_of(p), "default_model": p.model, "family": family_of(model_of(p), p.family),
            "strength": p.strength, "private": p.private, "configured": p.configured, "limit": p.limit,
            "used_today": used_today(p.id), "paused": _cooldown.get(p.id, 0) > time.time()}


# ---------------------------------------------------------------- appels


class Unavailable(RuntimeError):
    """Le fournisseur n'a rien produit (clé, limite, panne) : on peut passer au suivant."""


async def list_models(p: Provider) -> list[str]:
    if PROVIDER == "mock":
        return [p.model, p.model + "-large"]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{p.url}/models", headers={"Authorization": f"Bearer {p.key}"})
    if r.status_code != 200:
        raise RuntimeError(f"{p.name} a répondu {r.status_code}")
    data = r.json().get("data", [])
    skip = ("whisper", "tts", "embed", "guard", "moderation", "ocr", "transcri", "speech", "audio", "image", "vision-preview")
    ids = [m.get("id", "") for m in data if m.get("id") and not any(x in m.get("id", "").lower() for x in skip)
           and m.get("active", True) is not False]
    return sorted(set(i.removeprefix("models/") for i in ids))


async def stream(p: Provider, messages: list[dict], model: str | None = None, stats: dict | None = None) -> AsyncIterator[str]:
    """Flux de texte (format OpenAI, SSE). Lève Unavailable si rien n'a été produit."""
    model = model or model_of(p)
    if PROVIDER == "mock":
        reply = f"[curious] ({p.name}, mode test) Voici une réponse plus approfondie, venue de l'extérieur."
        if "RELECTEUR" in messages[0]["content"]:
            reply = "Verdict : OK\nAucun problème bloquant.\nNon vérifiable : rien."
        for w in re.findall(r"\S+\s*", reply):
            yield w
        count(p.id)
        if stats is not None:
            stats.clear(); stats.update(tokens=12, tok_s=40.0, provider=p.id, name=p.name, model=model)
        return
    payload = {"model": model, "messages": messages, "stream": True, "temperature": 0.6, "max_tokens": MAX_TOKENS}
    headers = {"Authorization": f"Bearer {p.key}", "Accept": "text/event-stream"}
    t0, first, n = time.time(), None, 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15, read=120)) as client:
            async with client.stream("POST", f"{p.url}/chat/completions", json=payload, headers=headers) as r:
                if r.status_code != 200:
                    body = (await r.aread()).decode(errors="replace")[:300]
                    if r.status_code in (401, 403):
                        raise Unavailable(f"clé API {p.name} refusée")
                    if r.status_code == 429:
                        _cooldown[p.id] = time.time() + 120
                        raise Unavailable(f"limite de l'offre {p.name} atteinte pour le moment")
                    if r.status_code == 404 and "model" in body.lower():
                        raise Unavailable(f"le modèle « {model} » n'existe pas chez {p.name}")
                    if r.status_code >= 500:
                        _cooldown[p.id] = time.time() + 60
                    raise Unavailable(f"{p.name} a répondu {r.status_code} : {body[:160]}")
                count(p.id)
                usage: dict = {}
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
    except httpx.HTTPError as e:
        if not n:
            _cooldown[p.id] = time.time() + 60
            raise Unavailable(f"{p.name} injoignable ({e.__class__.__name__})") from e
        raise
    if not n:
        raise Unavailable(f"{p.name} n'a rien répondu")
    dur = time.time() - (first or t0)
    toks = usage.get("completion_tokens", n)
    if stats is not None:
        stats.clear()
        stats.update(tokens=toks, tok_s=round(toks / dur, 1) if dur > 0 else None, provider=p.id, name=p.name, model=model,
                     prompt_tokens=usage.get("prompt_tokens"), total_s=round(time.time() - t0, 2))


async def stream_chain(providers: list[Provider], messages: list[dict], used: dict, model: str | None = None) -> AsyncIterator[str]:
    """Essaie les fournisseurs dans l'ordre ; passe au suivant tant que rien n'a été écrit.
    `used` reçoit le fournisseur qui a répondu (+ stats), et `used["skipped"]` les échecs."""
    errors = []
    for i, p in enumerate(providers):
        got = False
        try:
            async for t in stream(p, messages, model if i == 0 else None, used.setdefault("stats", {})):
                got = True
                yield t
            used.update(id=p.id, name=p.name, model=used["stats"].get("model", model_of(p)), skipped=errors)
            return
        except Unavailable as e:
            if got:
                raise
            log.info("relais : %s", e)
            errors.append(str(e))
    used["skipped"] = errors
    raise Unavailable(" ; ".join(errors) or "aucun fournisseur distant disponible")
