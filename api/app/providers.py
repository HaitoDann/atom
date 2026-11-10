"""Fournisseurs d'IA distants (API compatibles OpenAI) : plusieurs à la fois, avec relais automatique.

Configuration dans .env :
- le fournisseur principal historique : ATOM_REMOTE_NAME / _URL / _MODEL / _API_KEY / _DAILY_LIMIT ;
- des fournisseurs en plus : il suffit de ATOM_<ID>_API_KEY pour un fournisseur connu (PRESETS) ;
  ATOM_PROVIDERS=… sert pour les autres ou pour fixer l'ordre. Pour chacun : ATOM_<ID>_API_KEY (obligatoire) et au besoin _MODEL, _URL, _LIMIT, _FAMILY, _STRENGTH, _PRIVATE.
  Les fournisseurs connus (PRESETS) ont déjà leur adresse, un modèle par défaut et leur famille.

Chaque fournisseur a :
- un quota quotidien à lui ;
- une famille de modèles (llama, qwen, gemini…) : l'atelier fait relire par une autre famille ;
- une force (1 à 3) : l'arbitre n'est jamais le plus faible ;
- un drapeau « private » : s'il est faux, il ne reçoit jamais tes souvenirs, documents ni fichiers,
  même si le mode hybride l'autorise (ex. offres gratuites qui peuvent réutiliser les données).
"""

from __future__ import annotations

import asyncio
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
    listed = [p.strip().lower() for p in os.getenv("ATOM_PROVIDERS", "").split(",") if p.strip()]
    # Un fournisseur connu dont la clé est présente est activé même sans ATOM_PROVIDERS.
    listed += [pid for pid in PRESETS if pid not in listed and _env(pid, "API_KEY")]
    for pid in listed:
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

# Taille de requête tolérée (tokens, question + réponse) : les offres gratuites limitent les tokens par minute.
BUDGETS = {"groq": 7000, "github": 7500, "cerebras": 30000, "gemini": 100000, "openrouter": 30000, "mistral": 30000}


def budget(p: Provider) -> int:
    v = os.getenv(f"ATOM_{p.id.upper()}_BUDGET")
    return int(v) if v and v.isdigit() else BUDGETS.get(p.id, 30000)


def get(pid: str) -> Provider | None:
    return next((p for p in ALL if p.id == pid), None)


# ---------------------------------------------------------------- réglages par fournisseur (modèle choisi)


def model_of(p: Provider) -> str:
    m = db.kv_get(f"prov:model:{p.id}")
    if not m and ALL and p is ALL[0]:
        # ancien réglage du mode hybride (avant les fournisseurs multiples)
        try:
            m = json.loads(db.kv_get("hybrid") or "{}").get("model") or ""
        except ValueError:
            m = ""
    return m or p.model


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


def soonest_resume(sensitive: bool = False) -> float | None:
    """Secondes avant qu'un fournisseur en pause (limite par minute, panne passagère) redevienne disponible."""
    now = time.time()
    waits = [_cooldown[p.id] - now for p in ALL if p.configured and quota_left(p.id) > 0
             and (p.private or not sensitive) and _cooldown.get(p.id, 0) > now]
    return min(waits) if waits else None


def available(p: Provider, sensitive: bool = False) -> bool:
    return (p.configured and quota_left(p.id) > 0 and _cooldown.get(p.id, 0) < time.time()
            and (p.private or not sensitive))


# ---- santé mesurée : latence et réussite récentes (sur les vrais appels, pas sur la réputation du modèle)
HEALTH: dict[str, dict] = {}
CODE_FAMILIES = {"gpt": 0.4, "qwen": 0.4, "deepseek": 0.4, "claude": 0.4, "llama": 0.1, "mistral": 0.2, "gemini": 0.3}


def record(pid: str, ok: bool, latency: float | None = None, err: str = "") -> None:
    h = HEALTH.setdefault(pid, {"ok": 0, "ko": 0, "lat": None, "consec": 0, "recent": [], "err": ""})
    h["recent"] = (h["recent"] + [1 if ok else 0])[-20:]
    if ok:
        h["ok"] += 1; h["consec"] = 0
        if latency is not None:
            h["lat"] = latency if h["lat"] is None else h["lat"] * 0.7 + latency * 0.3
    else:
        h["ko"] += 1; h["consec"] += 1; h["err"] = err[:160]


TASKS = ("simple", "complexe", "code", "long", "agent")


def route_prefs() -> dict[str, str]:
    """Fournisseur préféré par type de demande (réglé dans l'interface) : {"code": "groq", …}."""
    try:
        prefs = json.loads(db.kv_get("route:prefs") or "{}")
    except ValueError:
        return {}
    return {t: pid for t, pid in prefs.items() if t in TASKS and get(pid)}


def set_route_prefs(prefs: dict[str, str]) -> dict[str, str]:
    clean = {t: pid for t, pid in prefs.items() if t in TASKS and pid and get(pid)}
    db.kv_set("route:prefs", json.dumps(clean))
    return clean


def estimate_tokens(messages: list[dict] | None) -> int:
    """Estimation grossière (≈ 3,5 caractères par token en français) de la question, plus la réponse attendue."""
    chars = sum(len(str(m.get("content") or "")) for m in messages or [])
    return int(chars / 3.5) + MAX_TOKENS


def assess(p: Provider, task: str | None = None, est_tokens: int = 0) -> tuple[float, list[str]]:
    """Score (plus c'est haut, plus on essaie tôt) et raisons lisibles du classement.
    La force estimée du modèle est corrigée par les mesures réelles, la nature de la tâche, la taille et le quota."""
    h = HEALTH.get(p.id, {})
    why: list[str] = []
    strength = float(p.strength)
    lat = h.get("lat")
    if task == "simple":
        # Question courte : la vitesse compte plus que la puissance.
        sc = 1 + 0.5 * strength
        if lat:
            sc += max(-1.0, min(1.0, (3 - lat) / 3))
            why.append(f"rapide ({lat:.1f} s)" if lat < 2 else f"latence {lat:.1f} s")
    else:
        sc = strength
        if task in ("complexe", "long", "agent"):
            sc += 0.3 * (strength - 2)
            if strength >= 3:
                why.append("modèle fort")
        if lat:
            sc -= min(0.8, max(0.0, (lat - 4) / 10))
    if task in ("code", "agent"):
        bonus = CODE_FAMILIES.get(family_of(model_of(p), p.family), 0)
        if bonus:
            sc += bonus
            why.append("bon en code")
    rec = h.get("recent") or []
    if len(rec) >= 3:
        rate = sum(rec) / len(rec)
        sc -= 1.5 * (1 - rate)
        if rate < 0.8:
            why.append(f"{round(100 * rate)} % de réussite")
    if h.get("consec"):
        sc -= 0.4 * min(3, h["consec"])
        why.append(f"{h['consec']} échec(s) d'affilée")
    if est_tokens and est_tokens > budget(p):
        sc -= 3
        why.append(f"requête trop longue pour l'offre (~{est_tokens} > {budget(p)} tokens)")
    if p.limit:
        left = quota_left(p.id) / p.limit
        if left < 0.2:
            sc -= (0.2 - left) * 5          # on épargne un fournisseur presque épuisé
            why.append(f"quota presque épuisé ({quota_left(p.id)} restants)")
    if task and route_prefs().get(task) == p.id:
        sc += 2
        why.insert(0, f"préféré pour « {task} »")
    return sc, why


def score(p: Provider, task: str | None = None) -> float:
    return assess(p, task)[0]


def plan(first: str | None = None, sensitive: bool = False, exclude: set[str] | None = None, task: str | None = None,
         est_tokens: int = 0) -> list[dict]:
    """Ordre d'essai expliqué : [{provider, score, why}]. Le fournisseur demandé passe en tête s'il va bien."""
    exclude = exclude or set()
    prefs = route_prefs()
    rows = []
    for p in ALL:
        if p.id in exclude or not available(p, sensitive):
            continue
        sc, why = assess(p, task, est_tokens)
        healthy = HEALTH.get(p.id, {}).get("consec", 0) < 2 and not (est_tokens and est_tokens > budget(p))
        # Priorité : la préférence pour ce type de demande, puis le fournisseur principal, puis le score.
        rank = 0 if healthy and task and prefs.get(task) == p.id else 1 if healthy and p.id == first else 2
        if rank == 1:
            why.insert(0, "fournisseur principal")
        rows.append({"provider": p, "score": round(sc, 2), "why": why, "pinned": rank < 2, "rank": rank})
    rows.sort(key=lambda r: (r["rank"], -r["score"]))
    return rows


def chain(first: str | None = None, sensitive: bool = False, exclude: set[str] | None = None, task: str | None = None,
          est_tokens: int = 0) -> list[Provider]:
    """Ordre d'essai : le fournisseur demandé d'abord (sauf s'il échoue en ce moment), puis par score décroissant."""
    return [r["provider"] for r in plan(first, sensitive, exclude, task, est_tokens)]


def explain(rows: list[dict]) -> str:
    """Raison courte du premier choix, pour le journal de consommation."""
    if not rows:
        return ""
    why = rows[0]["why"]
    return ", ".join(why[:3]) if why else "meilleur score"


def restore_health() -> None:
    """Au démarrage : reconstitue la santé de chaque fournisseur à partir de ses derniers appels journalisés."""
    from . import usage
    for p in ALL:
        try:
            calls = usage.last_calls(p.id)
        except Exception:
            log.warning("santé des fournisseurs non restaurée", exc_info=True)
            return
        for c in calls:
            record(p.id, bool(c["ok"]), c["first_s"], c["error"] or "")


def describe(p: Provider) -> dict:
    return {"id": p.id, "name": p.name, "model": model_of(p), "default_model": p.model, "family": family_of(model_of(p), p.family),
            "strength": p.strength, "private": p.private, "configured": p.configured, "limit": p.limit,
            "used_today": used_today(p.id), "paused": _cooldown.get(p.id, 0) > time.time(),
            "health": _health_public(p.id)}


def _health_public(pid: str) -> dict:
    h = HEALTH.get(pid)
    if not h:
        return {}
    rec = h["recent"]
    return {"latency": round(h["lat"], 1) if h["lat"] else None, "success": round(100 * sum(rec) / len(rec)) if rec else None,
            "calls": h["ok"] + h["ko"], "last_error": h["err"] if h["consec"] else ""}


# ---------------------------------------------------------------- appels


class Unavailable(RuntimeError):
    """Le fournisseur n'a rien produit (clé, limite, panne) : on peut passer au suivant."""


class RateLimited(Unavailable):
    """Limite par minute atteinte : réessayer après `wait` secondes."""

    def __init__(self, msg: str, wait: float = 60):
        super().__init__(msg)
        self.wait = wait


class TooLarge(Unavailable):
    """Requête trop grosse pour l'offre du fournisseur : on peut réessayer en plus court."""


CATALOGS = {"github": "https://models.github.ai/catalog/models"}   # GitHub n'a pas de /models au format OpenAI


async def list_models(p: Provider) -> list[str]:
    if PROVIDER == "mock":
        return [p.model, p.model + "-large"]
    url = CATALOGS.get(p.id) or f"{p.url}/models"
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        r = await client.get(url, headers={"Authorization": f"Bearer {p.key}", "Accept": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"{p.name} a répondu {r.status_code}")
    try:
        body = r.json()
    except ValueError as e:
        raise RuntimeError(f"{p.name} : liste des modèles illisible") from e
    data = body if isinstance(body, list) else body.get("data") or body.get("models") or []
    skip = ("whisper", "tts", "embed", "guard", "moderation", "ocr", "transcri", "speech", "audio", "image", "vision-preview")
    ids = []
    for m in data:
        mid = (m.get("id") or m.get("name") or "") if isinstance(m, dict) else str(m)
        if not mid or any(x in mid.lower() for x in skip) or (isinstance(m, dict) and m.get("active", True) is False):
            continue
        if isinstance(m, dict) and m.get("supported_output_modalities") and "text" not in m["supported_output_modalities"]:
            continue
        ids.append(mid.removeprefix("models/"))
    if p.id == "openrouter":
        ids = [i for i in ids if i.endswith(":free")]   # seulement les modèles gratuits : aucune dépense possible
    return sorted(set(ids))


# ---------------------------------------------------------------- modèle disparu : remplacement automatique

ODD = ("embed", "tts", "whisper", "guard", "moderation", "image", "audio", "vision", "ocr", "transcri", "speech",
       "realtime", "search", "computer-use", "instruct-v0", "lite-preview-02")


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[-_:./@]", name.lower()) if t]


def pick_replacement(old: str, available: list[str]) -> str | None:
    """Le modèle disponible le plus proche de l'ancien : même lignée (préfixe), même gabarit (flash, mini, 70b…),
    version la plus récente ; jamais un modèle spécialisé (images, audio, embeddings…) ni une préversion si on peut l'éviter."""
    old_t = _tokens(old.split("/")[-1])
    if not old_t:
        return None
    sizes = {t for t in old_t if t in ("flash", "pro", "mini", "nano", "small", "medium", "large", "lite", "turbo", "instant",
                                       "versatile") or re.fullmatch(r"\d+b", t)}

    def score(m: str) -> tuple:
        t = _tokens(m.split("/")[-1])
        same_line = t[:1] == old_t[:1]
        shared = len({x for x in set(t) & set(old_t) if not x.isdigit()})   # les chiffres de version ne comptent pas
        size_match = len(sizes & set(t))
        preview = any(x in t for x in ("preview", "exp", "experimental", "beta"))
        version = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", m.split("/")[-1])[:2]] or [0.0]
        return (same_line, size_match, not preview, version, shared)

    cands = [m for m in available if m != old and not any(x in m.lower() for x in ODD)]
    cands = [m for m in cands if _tokens(m.split("/")[-1])[:1] == old_t[:1]] or []
    return max(cands, key=score) if cands else None


_replacing: set[str] = set()


def _schedule_replace(p: "Provider", model: str) -> None:
    try:
        from . import jobs
        if p.id not in _replacing:
            jobs.background(replace_model(p, model))
    except RuntimeError:     # pas de boucle asyncio (appel hors serveur)
        pass


async def replace_model(p: "Provider", missing: str) -> str | None:
    """Remplace un modèle disparu par le plus proche disponible, et prévient l'utilisateur. Renvoie le nouveau modèle."""
    from . import hybrid, notify
    if not hybrid.settings().get("auto_replace", True) or p.id in _replacing or model_of(p) != missing:
        return None
    _replacing.add(p.id)
    try:
        try:
            available = await list_models(p)
        except Exception as e:  # noqa: BLE001
            log.warning("remplacement du modèle %s : liste indisponible (%s)", p.name, e)
            return None
        new = pick_replacement(missing, available)
        if not new:
            log.warning("remplacement du modèle %s : aucun modèle proche de %s", p.name, missing)
            await notify.send("⚠️ Modèle disparu", f"{p.name} ne propose plus « {missing} » et aucun modèle proche n'a été "
                              "trouvé. Choisis-en un dans Réglages → Mode hybride.", tags="warning")
            return None
        set_model(p.id, new)
        _cooldown.pop(p.id, None)
        _ping_cache.pop(p.id + missing, None)
        hist = json.loads(db.kv_get("model_replacements") or "[]")
        hist = (hist + [{"at": time.time(), "provider": p.id, "old": missing, "new": new}])[-20:]
        db.kv_set("model_replacements", json.dumps(hist))
        log.info("%s : modèle « %s » disparu, remplacé par « %s »", p.name, missing, new)
        await notify.send("🔄 Modèle remplacé", f"{p.name} ne propose plus « {missing} ». Atom utilise désormais « {new} ». "
                          "Tu peux en choisir un autre dans Réglages → Mode hybride.", tags="arrows_counterclockwise")
        return new
    finally:
        _replacing.discard(p.id)


def replacements() -> list[dict]:
    try:
        return json.loads(db.kv_get("model_replacements") or "[]")
    except ValueError:
        return []


_ping_cache: dict[str, tuple[float, str]] = {}


async def ping(p: Provider) -> str:
    """Vérifie la clé et le modèle par un appel minimal (1 jeton), mis en cache 30 min. Renvoie "" si OK."""
    hit = _ping_cache.get(p.id + model_of(p))
    if hit and time.time() - hit[0] < 1800:
        return hit[1]
    err = ""
    if PROVIDER != "mock":
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(f"{p.url}/chat/completions", headers={"Authorization": f"Bearer {p.key}"},
                                      json={"model": model_of(p), "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1})
            if r.status_code in (401, 403):
                err = "clé refusée"
            elif r.status_code == 404 or (r.status_code == 400 and "model" in r.text.lower()):
                err = "modèle introuvable"
            elif r.status_code == 429:
                err = ""   # limite momentanée : la clé et le modèle sont bons
            elif r.status_code != 200:
                err = f"a répondu {r.status_code}"
        except httpx.HTTPError as e:
            err = f"injoignable ({e.__class__.__name__})"
    _ping_cache[p.id + model_of(p)] = (time.time(), err)
    return err


async def stream(p: Provider, messages: list[dict], model: str | None = None, stats: dict | None = None,
                 max_tokens: int | None = None) -> AsyncIterator[str]:
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
            stats.clear(); stats.update(tokens=12, tok_s=40.0, provider=p.id, name=p.name, model=model, finish_reason="stop")
        return
    payload = {"model": model, "messages": messages, "stream": True, "temperature": 0.6, "max_tokens": max_tokens or MAX_TOKENS}
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
                        # Erreur de configuration, pas une panne passagère : écarté 10 min (atelier, orchestration),
                        # et Atom cherche un modèle de remplacement en tâche de fond (réglage auto_replace).
                        _cooldown[p.id] = time.time() + 600
                        _schedule_replace(p, model)
                        raise Unavailable(f"le modèle « {model} » n'existe pas chez {p.name}")
                    if r.status_code >= 500:
                        _cooldown[p.id] = time.time() + 60
                    raise Unavailable(f"{p.name} a répondu {r.status_code} : {body[:160]}")
                count(p.id)
                usage: dict = {}
                finish = None
                other: list[str] = []   # lignes hors SSE : certains fournisseurs renvoient un JSON entier
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        if line.strip():
                            other.append(line)
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    if chunk.get("error") and not n:
                        raise Unavailable(f"{p.name} : {str(chunk['error'])[:160]}")
                    usage = chunk.get("usage") or usage
                    for ch in chunk.get("choices") or []:
                        finish = ch.get("finish_reason") or finish
                        text = (ch.get("delta") or {}).get("content") or ""
                        if text:
                            first = first or time.time()
                            n += 1
                            yield text
                if not n and other:
                    try:
                        body = json.loads("\n".join(other))
                        usage = body.get("usage") or usage
                        choice = (body.get("choices") or [{}])[0]
                        finish = choice.get("finish_reason") or finish
                        text = (choice.get("message") or {}).get("content") or ""
                        if body.get("error"):
                            raise Unavailable(f"{p.name} : {str(body['error'])[:160]}")
                    except ValueError:
                        text = ""
                    if text:
                        first = time.time()
                        n = 1
                        yield text
    except httpx.HTTPError as e:
        if not n:
            _cooldown[p.id] = time.time() + 60
            raise Unavailable(f"{p.name} injoignable ({e.__class__.__name__})") from e
        raise
    if not n:
        log.warning("%s : réponse vide (%s)", p.name, (other[0][:200] if "other" in locals() and other else "aucune donnée"))
        raise Unavailable(f"{p.name} n'a rien répondu" + (f" ({other[0][:120]})" if "other" in locals() and other else ""))
    dur = time.time() - (first or t0)
    toks = usage.get("completion_tokens", n)
    if stats is not None:
        stats.clear()
        stats.update(tokens=toks, tok_s=round(toks / dur, 1) if dur > 0 else None, provider=p.id, name=p.name, model=model,
                     prompt_tokens=usage.get("prompt_tokens"), total_s=round(time.time() - t0, 2),
                     finish_reason=locals().get("finish"))


async def chat_tools(p: Provider, messages: list[dict], tools: list[dict], max_tokens: int = 4096) -> dict:
    """Appel non streamé avec outils natifs (function calling, format OpenAI). Renvoie le message de l'assistant.
    Journalisé dans usage.py (tâche « agent »)."""
    from . import usage
    t0 = time.time()
    meta: dict = {}
    try:
        msg = await _chat_tools(p, messages, tools, max_tokens, meta)
    except Unavailable as e:
        usage.record(p.id, model=model_of(p), task="agent", ok=False, total_s=time.time() - t0, error=str(e))
        raise
    usage.record(p.id, model=model_of(p), task="agent", ok=True, first_s=time.time() - t0, total_s=time.time() - t0,
                 prompt_tokens=meta.get("prompt_tokens"), completion_tokens=meta.get("completion_tokens"))
    return msg


async def _chat_tools(p: Provider, messages: list[dict], tools: list[dict], max_tokens: int, meta: dict) -> dict:
    if PROVIDER == "mock":
        return _mock_tools(messages)
    model = model_of(p)
    payload = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto",
               "temperature": 0.2, "max_tokens": max_tokens}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15, read=180)) as client:
                t_call = time.time()
                r = await client.post(f"{p.url}/chat/completions", json=payload, headers={"Authorization": f"Bearer {p.key}"})
        except httpx.HTTPError as e:
            _cooldown[p.id] = time.time() + 60
            raise Unavailable(f"{p.name} injoignable ({e.__class__.__name__})") from e
        if r.status_code == 429 and attempt < 2:
            # limite par minute : si le fournisseur dit d'attendre peu, on attend plutôt que d'abandonner
            try:
                wait = float(r.headers.get("retry-after") or 0)
            except ValueError:
                wait = 0
            m = re.search(r"try again in ([\d.]+)s", r.text)
            wait = wait or (float(m.group(1)) if m else 0)
            if 0 < wait <= 30:
                await asyncio.sleep(wait + 0.5)
                continue
        break
    if r.status_code != 200:
        body = r.text[:300]
        low = body.lower()
        if r.status_code == 413 or "request too large" in low or "context_length" in low or "maximum context" in low \
                or ("tokens per minute" in low and r.status_code != 429):
            raise TooLarge(f"requête trop longue pour l'offre {p.name}")
        if r.status_code in (401, 403):
            raise Unavailable(f"clé API {p.name} refusée")
        if r.status_code == 429:
            m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", body)
            wait = (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else float(r.headers.get("retry-after") or 60)
            per_day = "per day" in low or "tokens per day" in low or "requests per day" in low
            raise RateLimited(f"limite {'du jour' if per_day else 'par minute'} de l'offre {p.name}", wait if not per_day else 99999)
        if r.status_code >= 500:
            _cooldown[p.id] = time.time() + 60
        raise Unavailable(f"{p.name} a répondu {r.status_code} : {body[:200]}")
    count(p.id)
    record(p.id, True, time.time() - t_call)
    try:
        data = r.json()
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        meta.update(data.get("usage") or {})
    except (ValueError, AttributeError) as e:
        snippet = re.sub(r"\s+", " ", r.text[:160])
        log.warning("%s : réponse illisible (%s) : %s", p.name, r.headers.get("content-type"), snippet)
        raise Unavailable(f"{p.name} : réponse illisible ({r.headers.get('content-type', '?')} : {snippet[:100]})") from e
    return msg


async def stream_chain(providers: list[Provider], messages: list[dict], used: dict, model: str | None = None,
                       max_tokens: int | None = None, task: str | None = None, reason: str = "") -> AsyncIterator[str]:
    """Essaie les fournisseurs dans l'ordre ; passe au suivant tant que rien n'a été écrit.
    `used` reçoit le fournisseur qui a répondu (+ stats), et `used["skipped"]` les échecs.
    Chaque tentative est journalisée (usage.py), avec la raison du choix et la bascule éventuelle."""
    from . import usage
    errors = []
    prev: str | None = None
    for i, p in enumerate(providers):
        got = False
        t0, first_at = time.time(), None
        why = reason if i == 0 else f"bascule automatique : {errors[-1][:120]}" if errors else "relais"
        try:
            async for t in stream(p, messages, model if i == 0 else None, used.setdefault("stats", {}), max_tokens):
                got = True
                first_at = first_at or time.time()
                yield t
            first_s = (first_at or time.time()) - t0
            record(p.id, True, first_s)
            st = used["stats"]
            used.update(id=p.id, name=p.name, model=st.get("model", model_of(p)), skipped=errors)
            usage.record(p.id, model=st.get("model", model_of(p)), task=task, ok=True, first_s=first_s,
                         total_s=time.time() - t0, prompt_tokens=st.get("prompt_tokens") or estimate_tokens(messages) - MAX_TOKENS,
                         completion_tokens=st.get("tokens"), reason=why, fallback_from=prev)
            return
        except Unavailable as e:
            record(p.id, False, err=str(e))
            usage.record(p.id, model=model_of(p), task=task, ok=False, total_s=time.time() - t0, error=str(e),
                         reason=why, fallback_from=prev)
            if got:
                raise
            log.info("relais : %s", e)
            errors.append(str(e))
            prev = p.id
    used["skipped"] = errors
    raise Unavailable(" ; ".join(errors) or "aucun fournisseur distant disponible")


CONTINUE_PROMPT = ("Ta réponse a été coupée faute de place. Continue EXACTEMENT là où tu t'es arrêté, au caractère près, "
                   "sans rien répéter, sans introduction ni commentaire. Si tu étais dans un bloc de code, reste dans ce bloc.")


async def stream_complete(providers: list[Provider], messages: list[dict], used: dict, model: str | None = None,
                          max_tokens: int | None = None, task: str | None = None, reason: str = "",
                          continuations: int | None = None) -> AsyncIterator[str]:
    """Comme stream_chain, mais si la réponse est coupée faute de place (finish_reason = length), redemande la suite
    au même fournisseur (jusqu'à ATOM_MAX_CONTINUATIONS fois) : une page web ou un long fichier arrive en entier."""
    from .config import MAX_CONTINUATIONS
    left = MAX_CONTINUATIONS if continuations is None else continuations
    text = ""
    async for t in stream_chain(providers, messages, used, model, max_tokens, task, reason):
        text += t
        yield t
    while left > 0 and (used.get("stats") or {}).get("finish_reason") == "length" and used.get("id"):
        left -= 1
        p = next((x for x in providers if x.id == used["id"]), None) or get(used["id"])
        if not p:
            break
        log.info("réponse coupée chez %s : reprise automatique", p.name)
        used["continued"] = used.get("continued", 0) + 1
        follow = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": CONTINUE_PROMPT}]
        part: dict = {}
        async for t in stream_chain([p], follow, part, used.get("model"), max_tokens, task, "reprise après coupure"):
            text += t
            yield t
        used["stats"] = part.get("stats", {})


def _mock_tools(messages: list[dict]) -> dict:
    """Mode test : enchaîne list → read → edit → done avec de vrais appels d'outils."""
    strip = lambda t: "\n".join(l for l in t.split("\n") if not l.startswith("<<<"))   # encadrement « contenu externe »
    results = [strip(m["content"]) for m in messages if m["role"] == "tool"]
    n = len(results)

    def call(name: str, args: dict) -> dict:
        return {"role": "assistant", "content": f"Étape {n + 1}.",
                "tool_calls": [{"id": f"c{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
    if n == 0:
        return call("list", {"dir": "./"})
    if n == 1:
        first = next((l for l in results[0].split("\n") if l and not l.endswith("/")), "")
        return call("read", {"path": first})
    if n == 2:
        path = results[1].split(" (lignes")[0]
        line = re.search(r"\s+1\| (.*)", results[1])
        old = line.group(1) if line else ""
        return call("edit", {"path": path, "old": old, "new": "# modifié par l'agent\n" + old})
    return call("done", {"summary": "Commentaire ajouté (outils natifs)."})
