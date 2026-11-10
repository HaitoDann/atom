"""Brief du matin : chaque jour à l'heure choisie, un résumé envoyé sur Telegram et ntfy.

Sections (chacune activable) :
- rappels du jour ;
- météo (Open-Meteo, sans clé : géocodage de la ville puis prévisions du jour) ;
- serveur Proxmox (nœuds, invités arrêtés, stockages presque pleins, alertes) ;
- fournisseurs d'IA (appel minimal à chacun : clé refusée, modèle disparu, injoignable) ;
- actualités (SearXNG, quelques titres par sujet) ;
- souvenirs récents.
Option « mot d'Atom » : le modèle écrit une courte introduction chaleureuse à partir des faits (repli : le brief brut).
Le brief est aussi conservé dans une conversation « Brief du matin » pour le relire dans l'interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime

import httpx

from . import db, notify
from .config import PROVIDER

log = logging.getLogger("atom.brief")

DEFAULTS = {
    "enabled": False,
    "time": "07:30",
    "days": [0, 1, 2, 3, 4, 5, 6],            # 0 = lundi
    "city": "",
    "news": "",                                # sujets séparés par des virgules ; vide = pas d'actualités
    "sections": {"agenda": True, "reminders": True, "weather": True, "server": True, "providers": True, "news": True, "memories": False},
    "intro": True,                             # mot d'Atom rédigé par le modèle
}
SECTION_NAMES = {"agenda": "Agenda du jour", "reminders": "Rappels du jour", "weather": "Météo", "server": "Serveur", "providers": "Fournisseurs d'IA",
                 "news": "Actualités", "memories": "Souvenirs récents"}

WMO = {0: "ciel dégagé", 1: "plutôt dégagé", 2: "partiellement nuageux", 3: "couvert", 45: "brouillard", 48: "brouillard givrant",
       51: "bruine légère", 53: "bruine", 55: "bruine forte", 61: "pluie faible", 63: "pluie", 65: "forte pluie",
       66: "pluie verglaçante", 67: "pluie verglaçante", 71: "neige faible", 73: "neige", 75: "forte neige", 77: "grésil",
       80: "averses", 81: "averses", 82: "fortes averses", 85: "averses de neige", 86: "averses de neige",
       95: "orages", 96: "orages avec grêle", 99: "orages avec grêle"}


def settings() -> dict:
    s = json.loads(json.dumps(DEFAULTS))
    try:
        raw = json.loads(db.kv_get("brief") or "{}")
    except ValueError:
        raw = {}
    for k, v in raw.items():
        if k == "sections" and isinstance(v, dict):
            s["sections"].update({x: bool(y) for x, y in v.items() if x in DEFAULTS["sections"]})
        elif k in DEFAULTS:
            s[k] = v
    return s


def save_settings(new: dict) -> dict:
    s = settings()
    for k, v in new.items():
        if k == "sections" and isinstance(v, dict):
            s["sections"].update({x: bool(y) for x, y in v.items() if x in DEFAULTS["sections"]})
        elif k in DEFAULTS and v is not None:
            s[k] = v
    try:
        h, m = (int(x) for x in str(s["time"]).split(":"))
        s["time"] = f"{min(23, max(0, h)):02d}:{min(59, max(0, m)):02d}"
    except ValueError:
        s["time"] = DEFAULTS["time"]
    s["days"] = sorted({int(d) for d in s.get("days", []) if str(d).isdigit() and 0 <= int(d) <= 6})
    s["city"] = str(s.get("city", ""))[:80].strip()
    s["news"] = str(s.get("news", ""))[:200].strip()
    db.kv_set("brief", json.dumps(s))
    return s


# ---------------------------------------------------------------- sections

def section_reminders() -> str:
    from .reminders import TZ, human, now_local
    today = now_local().date()
    rows = [r for r in db.list_reminders("pending", limit=100) if datetime.fromtimestamp(r["due_at"], TZ).date() == today]
    late = [r for r in db.unacked_reminders() if r["due_at"] < time.time() - 3600]
    lines = [f"- ⚠️ Pas encore fait : {r['text']} (rappel de {human(r['due_at'])})" for r in late[:5]]
    if not rows:
        return "\n".join(lines + ["Aucun rappel aujourd'hui."]) if lines else "Aucun rappel aujourd'hui."
    return "\n".join(lines) + ("\n" if lines else "") + "\n".join(f"- {human(r['due_at']).replace("aujourd'hui à ", "")} : {r['text']}" for r in rows)


def section_agenda() -> str:
    from . import agenda
    return agenda.today_text() or "Rien de prévu aujourd'hui."


async def section_weather(city: str) -> str:
    if not city:
        return "Ville non renseignée (Réglages → Brief du matin)."
    if PROVIDER == "mock":
        return f"{city} : 8 °C → 14 °C, partiellement nuageux, pluie 20 %."
    async with httpx.AsyncClient(timeout=10) as c:
        g = (await c.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1, "language": "fr"})).json().get("results") or []
        if not g:
            return f"Ville introuvable : {city}."
        loc = g[0]
        f = (await c.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": loc["latitude"], "longitude": loc["longitude"], "timezone": "auto", "forecast_days": 1,
            "daily": "weather_code,temperature_2m_min,temperature_2m_max,precipitation_probability_max,wind_speed_10m_max",
        })).json()["daily"]
    desc = WMO.get(int(f["weather_code"][0]), "temps variable")
    rain = f["precipitation_probability_max"][0]
    wind = f["wind_speed_10m_max"][0]
    out = f"{loc['name']} : {f['temperature_2m_min'][0]:.0f} °C → {f['temperature_2m_max'][0]:.0f} °C, {desc}"
    out += f", pluie {rain:.0f} %" if rain is not None else ""
    out += f", vent jusqu'à {wind:.0f} km/h" if wind and wind >= 40 else ""
    return out + "."


async def section_server() -> str:
    from . import proxmox
    if not proxmox.configured():
        return ""
    await proxmox.poll()
    st = proxmox.state
    if not st["ok"]:
        return f"⚠️ Proxmox injoignable : {st['error']}."
    lines = []
    for n in st["nodes"]:
        lines.append(f"- {n['name']} : processeur {n['cpu']:.0f} %, mémoire {n['mem']:.0f} %, en marche depuis {proxmox._dur(n['uptime'])}")
    run = [g for g in st["guests"] if g["status"] == "running"]
    stop = [g for g in st["guests"] if g["status"] != "running"]
    lines.append(f"- Invités : {len(run)} en marche" + (f", arrêtés : {', '.join(g['name'] for g in stop)}" if stop else ""))
    full = [s for s in st["storages"] if s["pct"] >= 80]
    for s in full:
        lines.append(f"- ⚠️ Stockage {s['name']} rempli à {s['pct']:.0f} %")
    if proxmox.alerts():
        lines.append("- ⚠️ Alertes : " + " ; ".join(a["title"] for a in proxmox.alerts()))
    return "\n".join(lines)


async def section_providers() -> str:
    from . import providers
    confs = [p for p in providers.ALL if p.configured]
    if not confs:
        return ""
    errs = list(await asyncio.gather(*[providers.ping(p) for p in confs], return_exceptions=True))
    fixed = []
    for i, (p, e) in enumerate(zip(confs, errs, strict=True)):
        if e == "modèle introuvable":                 # modèle disparu : remplacement automatique (si activé)
            old = providers.model_of(p)
            new = await providers.replace_model(p, old)
            if new:
                fixed.append(f"- 🔄 {p.name} : « {old} » a disparu, remplacé par « {new} »")
                errs[i] = await providers.ping(p)
    bad = [(p, e) for p, e in zip(confs, errs, strict=True) if e]
    ok = len(confs) - len(bad)
    if not bad:
        return "\n".join([f"Tous opérationnels ({ok}/{len(confs)})."] + fixed)
    lines = [f"{ok}/{len(confs)} opérationnels."] + fixed
    for p, e in bad:
        lines.append(f"- ⚠️ {p.name} ({providers.model_of(p)}) : {e if isinstance(e, str) else e.__class__.__name__}"
                     + (" → choisis un autre modèle dans Réglages → Hybride" if "modèle" in str(e) else ""))
    return "\n".join(lines)


async def section_news(topics: str) -> str:
    from . import search
    subjects = [t.strip() for t in topics.split(",") if t.strip()][:3]
    if not subjects:
        return ""
    if not search.enabled():
        return "Recherche web non configurée."
    lines = []
    for t in subjects:
        try:
            res = await search.search(f"{t} actualité")
        except Exception as e:  # noqa: BLE001
            lines.append(f"- {t} : indisponible ({str(e)[:60]})")
            continue
        for r in res[:2]:
            lines.append(f"- {t} · [{r['title']}]({r['url']})")
    return "\n".join(lines)


def section_memories() -> str:
    rows = [m for m in db.list_memories() if m.get("created_at", 0) > time.time() - 7 * 86400]
    return "\n".join(f"- {m['content']}" for m in rows[-5:]) or ""


# ---------------------------------------------------------------- assemblage

async def build(s: dict | None = None) -> dict:
    """Construit le brief sans l'envoyer : {title, text, sections: {nom: texte}}."""
    from .reminders import JOURS, MOIS, now_local
    s = s or settings()
    on = s["sections"]
    jobs = {
        "agenda": (lambda: asyncio.sleep(0, section_agenda())) if on.get("agenda", True) else None,
        "reminders": (lambda: asyncio.sleep(0, section_reminders())) if on["reminders"] else None,
        "weather": (lambda: section_weather(s["city"])) if on["weather"] else None,
        "server": section_server if on["server"] else None,
        "providers": section_providers if on["providers"] else None,
        "news": (lambda: section_news(s["news"])) if on["news"] else None,
        "memories": (lambda: asyncio.sleep(0, section_memories())) if on["memories"] else None,
    }
    names = [k for k, f in jobs.items() if f]
    results = await asyncio.gather(*[jobs[k]() for k in names], return_exceptions=True)
    sections = {}
    for k, r in zip(names, results, strict=True):
        if isinstance(r, Exception):
            log.warning("brief : section %s en échec : %s", k, r)
            r = f"indisponible ({r.__class__.__name__})"
        if r:
            sections[k] = r
    n = now_local()
    title = f"☀️ Brief du {JOURS[n.weekday()]} {n.day} {MOIS[n.month - 1]}"
    body = "\n\n".join(f"**{SECTION_NAMES[k]}**\n{v}" for k, v in sections.items()) or "Rien de particulier aujourd'hui."
    intro = await _intro(body) if s.get("intro") else ""
    return {"title": title, "text": (intro + "\n\n" + body) if intro else body, "sections": sections, "intro": intro}


async def _intro(facts: str) -> str:
    """Deux phrases chaleureuses qui mettent en avant l'important ; vide si le modèle ne répond pas."""
    from . import llm, workshop
    if PROVIDER == "mock":
        return "Bonjour ! Voici l'essentiel pour bien commencer la journée."
    msgs = [{"role": "system", "content": "Tu es Atom, l'assistant personnel de l'utilisateur. En français, écris DEUX phrases "
                                          "au plus pour ouvrir son brief du matin : salue-le et mets en avant ce qui demande "
                                          "son attention (rappel, alerte, météo notable). N'invente rien, pas de liste, "
                                          "pas d'émotion entre crochets. /no_think"},
            {"role": "user", "content": facts[:3000]}]
    try:
        out = await asyncio.wait_for(_collect(llm.stream_chat(workshop._local_model(), msgs, task="brief")), timeout=180)
    except Exception as e:  # noqa: BLE001
        log.info("brief : introduction impossible (%s), envoi sans", e)
        return ""
    return workshop.TAG_RE.sub("", workshop.THINK_RE.sub("", out)).strip()[:500]


async def _collect(gen) -> str:
    return "".join([t async for t in gen])


async def send(s: dict | None = None) -> dict:
    """Construit, envoie sur les canaux configurés et range le brief dans sa conversation."""
    b = await build(s)
    cid = _conversation()
    db.add_message(cid, "assistant", f"**{b['title']}**\n\n{b['text']}", "joy")
    ok = await notify.send(b["title"], b["text"], cid, tags="sunny")
    db.kv_set("brief_last", json.dumps({"date": _today(), "at": time.time(), "sent": ok}))
    log.info("brief envoyé (%s), sections : %s", "ok" if ok else "aucun canal", ", ".join(b["sections"]))
    return {**b, "sent": ok, "conversation_id": cid, "channels": notify.enabled()}


def _conversation() -> int:
    v = db.kv_get("brief_conversation")
    if v and v.isdigit() and db.conversation_exists(int(v)):
        return int(v)
    cid = db.create_conversation("☀️ Brief du matin")
    db.kv_set("brief_conversation", str(cid))
    return cid


def _today() -> str:
    from .reminders import now_local
    return now_local().strftime("%Y-%m-%d")


def last() -> dict:
    try:
        return json.loads(db.kv_get("brief_last") or "{}")
    except ValueError:
        return {}


def due(s: dict, now: datetime, last_date: str | None) -> bool:
    """Vrai s'il faut envoyer maintenant : activé, bon jour, heure passée, pas déjà envoyé aujourd'hui.
    Si Atom démarre en retard, le brief part quand même dans les 4 heures qui suivent, une seule fois."""
    if not s["enabled"] or now.weekday() not in s["days"] or last_date == now.strftime("%Y-%m-%d"):
        return False
    h, m = (int(x) for x in s["time"].split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return 0 <= (now - target).total_seconds() < 4 * 3600


async def scheduler() -> None:
    from .reminders import now_local
    log.info("brief du matin : planificateur démarré")
    while True:
        try:
            s = settings()
            if due(s, now_local(), last().get("date")):
                await send(s)
        except Exception:
            log.exception("brief du matin")
        await asyncio.sleep(30)
