"""Accès au modèle : chat en streaming, appel JSON contraint, embeddings."""

from __future__ import annotations

import asyncio
import json
import random
import re
from typing import AsyncIterator

import httpx
import numpy as np

from .config import EMBED_MODEL, MAX_TOKENS, OLLAMA_URL, PROVIDER


class ModelMissing(RuntimeError):
    pass


def _raise_for(status: int, body: str, model: str) -> None:
    if status == 404 and "not found" in body:
        raise ModelMissing(
            f"Le modèle « {model} » n'est pas installé. "
            f"Lance : docker compose exec ollama ollama pull {model}"
        )
    raise RuntimeError(f"Ollama a répondu {status} : {body[:300]}")


async def stream_chat(model: str, messages: list[dict]) -> AsyncIterator[str]:
    if PROVIDER == "mock":
        async for t in _mock_stream(messages):
            yield t
        return
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,
        # num_predict borne la longueur : un petit modèle qui part en boucle s'arrête.
        "options": {"temperature": 0.7, "num_predict": MAX_TOKENS, "repeat_penalty": 1.12},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=300)) as client:
        async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
            if r.status_code != 200:
                _raise_for(r.status_code, (await r.aread()).decode(errors="replace"), model)
            async for line in r.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                text = chunk.get("message", {}).get("content", "")
                if text:
                    yield text
                if chunk.get("done"):
                    break


async def json_chat(model: str, messages: list[dict], schema: dict) -> dict:
    """Appel non streamé avec sortie JSON contrainte par un schéma."""
    if PROVIDER == "mock":
        return {}
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0.1, "num_predict": 400},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=300)) as client:
        r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    if r.status_code != 200:
        _raise_for(r.status_code, r.text, model)
    content = r.json().get("message", {}).get("content", "")
    content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


async def embed(texts: list[str], kind: str = "document") -> list[np.ndarray] | None:
    """Embeddings normalisés, ou None si le modèle d'embedding est indisponible.

    nomic-embed-text attend un préfixe de tâche : search_query / search_document.
    """
    if not texts:
        return []
    if PROVIDER == "mock":
        return [_mock_vec(t) for t in texts]
    prefix = "search_query: " if kind == "query" else "search_document: "
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=120)) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": [prefix + t for t in texts]},
            )
        if r.status_code != 200:
            return None
        vecs = r.json().get("embeddings") or []
    except (httpx.HTTPError, ValueError):
        return None
    out = []
    for v in vecs:
        a = np.asarray(v, dtype=np.float32)
        n = np.linalg.norm(a)
        out.append(a / n if n else a)
    return out if len(out) == len(texts) else None


async def installed_models() -> list[str]:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{OLLAMA_URL}/api/tags")
        r.raise_for_status()
    return [m["name"] for m in r.json().get("models", [])]


# ---------------------------------------------------------------- mode test


async def _mock_stream(messages: list[dict]) -> AsyncIterator[str]:
    user = messages[-1]["content"]
    emotion = random.choice(["talking", "joy", "surprise"])
    reply = (
        f"[{emotion}] (mode test) Tu m'as dit : **« {user} »**.\n\n"
        "| Élément | État |\n|---|---|\n| Streaming | ✅ |\n| Markdown | ✅ |\n"
    )
    for word in re.findall(r"\S+\s*", reply):
        await asyncio.sleep(0.04)
        yield word


def _mock_vec(text: str) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(text.lower())) % (2**32))
    v = rng.standard_normal(64).astype(np.float32)
    return v / np.linalg.norm(v)
