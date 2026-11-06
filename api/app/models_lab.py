"""Labo des modèles locaux : installer, comparer côte à côte, décharger, supprimer.

- install() télécharge un modèle via Ollama en arrière-plan (progression consultable).
- compare() pose les mêmes questions à plusieurs modèles, l'un après l'autre (jamais en parallèle :
  sur CPU, deux modèles à la fois se ralentiraient), et mesure chargement, délai avant le premier mot,
  vitesse d'écriture et de lecture.
- Après un comparatif, les modèles non retenus sont déchargés de la mémoire.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator

import httpx

from . import llm, providers
from .config import OLLAMA_URL, PROVIDER

SUGGESTED = [
    {"name": "qwen3:30b-a3b-instruct-2507-q4_K_M", "size_gb": 18.6,
     "note": "30 milliards de paramètres mais seulement ~3 actifs par mot : bien plus capable que les 4B, "
             "vitesse proche sur CPU. Demande ~19 Go de RAM libre."},
    {"name": "qwen2.5-coder:7b", "size_gb": 4.7, "note": "Spécialisé code : meilleur pour le mode Code, environ 2× plus lent qu'un 4B."},
    {"name": "gemma3:4b", "size_gb": 3.3, "note": "Même taille que ton modèle actuel, autre famille (Google) : utile pour comparer le style."},
    {"name": "qwen3:4b-instruct-2507-q4_K_M", "size_gb": 2.5, "note": "Le modèle par défaut d'Atom."},
]

PROMPTS = [
    {"id": "raisonnement", "label": "Raisonnement",
     "text": "Un train part à 14 h 10 et roule à 90 km/h. Un second part du même endroit à 14 h 40 à 120 km/h. "
             "À quelle heure le rattrape-t-il ? Explique brièvement le calcul."},
    {"id": "redaction", "label": "Rédaction",
     "text": "Écris un message court et chaleureux pour décliner une invitation à dîner samedi, en proposant une autre date."},
    {"id": "code", "label": "Code",
     "text": "Écris une fonction Python qui renvoie les doublons d'une liste en conservant l'ordre de première apparition, avec un exemple."},
    {"id": "connaissances", "label": "Connaissances",
     "text": "Explique en 5 phrases la différence entre un conteneur LXC et une machine virtuelle sur Proxmox."},
]

_pulls: dict[str, dict] = {}   # nom → {status, completed, total, error, done}


def pulls() -> list[dict]:
    return [{"name": k, **v} for k, v in _pulls.items()]


async def install(name: str) -> None:
    st = _pulls[name] = {"status": "démarrage", "completed": 0, "total": 0, "error": "", "done": False, "started": time.time()}
    if PROVIDER == "mock":
        for i in range(1, 6):
            await asyncio.sleep(0.2)
            st.update(status="téléchargement", completed=i * 20, total=100)
        st.update(status="terminé", done=True)
        return
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=600)) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/pull", json={"model": name, "stream": True}) as r:
                if r.status_code != 200:
                    raise RuntimeError((await r.aread()).decode(errors="replace")[:200])
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    ev = json.loads(line)
                    if ev.get("error"):
                        raise RuntimeError(ev["error"])
                    st["status"] = ev.get("status", st["status"])
                    if ev.get("total"):
                        st["total"], st["completed"] = ev["total"], ev.get("completed", 0)
        st.update(status="terminé", done=True)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "file does not exist" in msg or "not found" in msg.lower():
            msg = "modèle introuvable dans la bibliothèque Ollama (vérifie le nom sur ollama.com/library)"
        st.update(status="erreur", error=msg[:300], done=True)


async def delete(name: str) -> None:
    if PROVIDER == "mock":
        return
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.request("DELETE", f"{OLLAMA_URL}/api/delete", json={"model": name})
    if r.status_code not in (200, 404):
        raise RuntimeError(r.text[:200])


async def unload(name: str) -> None:
    """Libère la RAM occupée par un modèle (keep_alive = 0)."""
    if PROVIDER == "mock":
        return
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(f"{OLLAMA_URL}/api/generate", json={"model": name, "keep_alive": 0})
    except httpx.HTTPError:
        pass


async def compare(models: list[str], prompts: list[dict], keep: str | None = None) -> AsyncIterator[dict]:
    """Événements : start(model, prompt), token, result(stats), error, done."""
    for m in models:
        for p in prompts:
            yield dict(type="start", model=m, prompt=p["id"])
            t0, first, text = time.time(), None, ""
            try:
                if m.startswith("p:"):   # fournisseur distant (même question, sans aucune donnée personnelle)
                    prov = providers.get(m[2:])
                    if not prov or not prov.configured:
                        raise RuntimeError("fournisseur non configuré")
                    stats: dict = {}
                    gen = providers.stream(prov, [{"role": "user", "content": p["text"]}], None, stats)
                else:
                    stats = llm.last_stats
                    gen = llm.stream_chat(m, [{"role": "user", "content": p["text"] + " /no_think"}])
                async for tok in gen:
                    first = first or time.time()
                    text += tok
                    yield dict(type="token", model=m, prompt=p["id"], text=tok)
                s = dict(stats)
                if m.startswith("p:") and s.get("tokens") and first:
                    s["tok_s"] = round(s["tokens"] / max(0.01, time.time() - first), 1)   # mesuré côté Atom
                yield dict(type="result", model=m, prompt=p["id"], text=text,
                           first_s=round((first or time.time()) - t0, 2), wall_s=round(time.time() - t0, 2),
                           tok_s=s.get("tok_s"), prompt_tok_s=s.get("prompt_tok_s"), load_s=s.get("load_s"), tokens=s.get("tokens"))
            except Exception as e:  # noqa: BLE001
                yield dict(type="error", model=m, prompt=p["id"], message=str(e)[:300])
                break   # modèle en échec (absent, mémoire insuffisante) : on passe au suivant
        if keep and m != keep and not m.startswith("p:"):
            await unload(m)
    yield dict(type="done")
