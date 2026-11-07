"""Accès au modèle : chat en streaming, appel JSON contraint, embeddings."""

from __future__ import annotations

import asyncio
import json
import time
import random
import re
from typing import AsyncIterator

import httpx
import numpy as np

from .config import EMBED_MODEL, MAX_TOKENS, NUM_CTX, NUM_THREADS, OLLAMA_URL, PROVIDER

# Dernière mesure de vitesse renvoyée par Ollama (tokens/s, durée de lecture du prompt…)
last_stats: dict = {}


def _opts(**kw) -> dict:
    o = {"num_ctx": NUM_CTX, **kw}
    if NUM_THREADS > 0:
        o["num_thread"] = NUM_THREADS
    return o


class ModelMissing(RuntimeError):
    pass


def _raise_for(status: int, body: str, model: str) -> None:
    if status == 404 and "not found" in body:
        raise ModelMissing(
            f"Le modèle « {model} » n'est pas installé. "
            f"Lance : docker compose exec ollama ollama pull {model}"
        )
    raise RuntimeError(f"Ollama a répondu {status} : {body[:300]}")


async def stream_chat(model: str, messages: list[dict], task: str | None = None) -> AsyncIterator[str]:
    """Flux du modèle local (Ollama), journalisé dans usage.py comme fournisseur « local »."""
    from . import usage
    t0, first, ok, err = time.time(), None, False, ""
    last_stats.clear()
    try:
        async for t in _stream_chat(model, messages):
            first = first or time.time()
            yield t
        ok = True
    except GeneratorExit:   # réponse interrompue par l'utilisateur : l'appel a bien eu lieu
        ok = first is not None
        raise
    except Exception as e:
        err = str(e) or e.__class__.__name__
        raise
    finally:
        st = dict(last_stats) if ok else {}
        usage.record("local", model=model, task=task, ok=ok, first_s=(first - t0) if first else None,
                     total_s=time.time() - t0, prompt_tokens=st.get("prompt_tokens"), completion_tokens=st.get("tokens"),
                     error=err)


async def _stream_chat(model: str, messages: list[dict]) -> AsyncIterator[str]:
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
        "options": _opts(temperature=0.7, num_predict=MAX_TOKENS, repeat_penalty=1.12),
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
                    ev, ed = chunk.get("eval_count", 0), chunk.get("eval_duration", 0)
                    pc, pd = chunk.get("prompt_eval_count", 0), chunk.get("prompt_eval_duration", 0)
                    last_stats.clear()
                    last_stats.update(
                        tokens=ev, tok_s=round(ev / (ed / 1e9), 2) if ed else None,
                        prompt_tokens=pc, prompt_tok_s=round(pc / (pd / 1e9), 1) if pd else None,
                        load_s=round(chunk.get("load_duration", 0) / 1e9, 2),
                        total_s=round(chunk.get("total_duration", 0) / 1e9, 2),
                    )
                    break


async def json_chat(model: str, messages: list[dict], schema: dict, task: str = "memoire") -> dict:
    """Appel non streamé avec sortie JSON contrainte par un schéma (mémorisation, classement…).
    Journalisé comme appel « local » de tâche `task` : le travail en coulisse compte aussi dans la consommation."""
    from . import usage
    if PROVIDER == "mock":
        return {}
    t0 = time.time()
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": schema,
        "options": _opts(temperature=0.1, num_predict=400),
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=300)) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        if r.status_code != 200:
            _raise_for(r.status_code, r.text, model)
        data = r.json()
    except Exception as e:
        usage.record("local", model=model, task=task, ok=False, total_s=time.time() - t0, error=str(e) or e.__class__.__name__)
        raise
    usage.record("local", model=model, task=task, ok=True, total_s=time.time() - t0,
                 prompt_tokens=data.get("prompt_eval_count"), completion_tokens=data.get("eval_count"))
    content = data.get("message", {}).get("content", "")
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
    from . import usage
    prefix = "search_query: " if kind == "query" else "search_document: "
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=300)) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": [prefix + t for t in texts], "keep_alive": "24h",
                      "options": {k: v for k, v in _opts().items() if k == "num_thread"}},
            )
        if r.status_code != 200:
            usage.record("local", model=EMBED_MODEL, task="embedding", ok=False, total_s=time.time() - t0,
                         error=f"Ollama a répondu {r.status_code} : {r.text[:120]}")
            return None
        data = r.json()
        vecs = data.get("embeddings") or []
    except (httpx.HTTPError, ValueError) as e:
        usage.record("local", model=EMBED_MODEL, task="embedding", ok=False, total_s=time.time() - t0,
                     error=f"Ollama injoignable ({e.__class__.__name__})")
        return None
    usage.record("local", model=EMBED_MODEL, task="embedding", ok=True, total_s=time.time() - t0,
                 prompt_tokens=data.get("prompt_eval_count"), reason=f"{len(texts)} texte(s) · {kind}")
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
    if "cherche" in user.lower() and "Résultats d'une recherche web" not in messages[0]["content"]:
        reply = f"[[recherche {user[:60]}]]"
    elif "Résultats d'une recherche web" in messages[0]["content"]:
        reply = "[curious] (mode test) D'après ma recherche, voici ce que j'ai trouvé [1]."
    elif "rappel" in user.lower():
        from datetime import timedelta

        from .reminders import now_local

        due = (now_local() + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")
        reply = f"[joy] C'est noté, je te le rappelle dans une minute. [[rappel {due} | {user[:60]}]]"
    for word in re.findall(r"\S+\s*", reply):
        await asyncio.sleep(0.04)
        yield word


def _mock_vec(text: str) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(text.lower())) % (2**32))
    v = rng.standard_normal(64).astype(np.float32)
    return v / np.linalg.norm(v)
