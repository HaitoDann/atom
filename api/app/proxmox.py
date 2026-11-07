"""Surveillance du serveur Proxmox, en lecture seule.

Configuration (.env) :
  ATOM_PROXMOX_URL=https://192.168.1.10:8006
  ATOM_PROXMOX_TOKEN_ID=atom@pve!atom          (utilisateur@royaume!nom-du-jeton)
  ATOM_PROXMOX_TOKEN_SECRET=xxxxxxxx-xxxx-…
  ATOM_PROXMOX_VERIFY_TLS=0                    (certificat auto-signé de Proxmox : 0 par défaut)
Le jeton n'a besoin que du rôle PVEAuditor (lecture seule) : Atom ne peut rien démarrer, arrêter ni modifier.

Toutes les minutes : état des nœuds, des VM / conteneurs et des stockages ; historique de 24 h en mémoire ;
alertes (processeur ou mémoire hauts pendant 10 min, stockage presque plein, invité arrêté, nœud injoignable)
envoyées par Telegram et ntfy, avec une pause d'une heure par alerte et un message quand c'est rétabli.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque

import httpx

from . import db, notify, telegram

log = logging.getLogger("atom.proxmox")

URL = os.getenv("ATOM_PROXMOX_URL", "").rstrip("/")
TOKEN_ID = os.getenv("ATOM_PROXMOX_TOKEN_ID", "")
TOKEN_SECRET = os.getenv("ATOM_PROXMOX_TOKEN_SECRET", "")
VERIFY = os.getenv("ATOM_PROXMOX_VERIFY_TLS", "0").lower() in ("1", "true", "oui", "yes")
INTERVAL = int(os.getenv("ATOM_PROXMOX_INTERVAL", "60"))

DEFAULTS = {"cpu": 90, "mem": 90, "storage": 85, "minutes": 10, "notify": True, "guest_down": True}

state: dict = {"ok": False, "error": "", "updated": 0, "nodes": [], "guests": [], "storages": []}
history: dict[str, deque] = {}           # nœud → [(t, cpu %, mem %)] sur 24 h
_high_since: dict[str, float] = {}       # clé d'alerte → début du dépassement
_active: dict[str, dict] = {}            # alertes en cours
_last_sent: dict[str, float] = {}
_was_running: dict[str, bool] = {}
_fails = 0


def configured() -> bool:
    return bool(URL and TOKEN_ID and TOKEN_SECRET)


def settings() -> dict:
    s = dict(DEFAULTS)
    try:
        s.update({k: v for k, v in json.loads(db.kv_get("proxmox:settings") or "{}").items() if k in DEFAULTS})
    except ValueError:
        pass
    return s


def save_settings(new: dict) -> dict:
    s = settings()
    s.update({k: v for k, v in new.items() if k in DEFAULTS})
    db.kv_set("proxmox:settings", json.dumps(s))
    return s


async def _get(client: httpx.AsyncClient, path: str):
    r = await client.get(f"{URL}/api2/json{path}", headers={"Authorization": f"PVEAPIToken={TOKEN_ID}={TOKEN_SECRET}"})
    if r.status_code == 401:
        raise RuntimeError("jeton refusé (vérifie ATOM_PROXMOX_TOKEN_ID et _SECRET)")
    if r.status_code == 403:
        raise RuntimeError("droits insuffisants : donne le rôle PVEAuditor au jeton sur « / »")
    r.raise_for_status()
    return r.json().get("data")


def _pct(a, b) -> float:
    return round(100 * a / b, 1) if b else 0.0


async def poll() -> dict:
    """Relève l'état complet (appelé chaque minute, et à la demande)."""
    global _fails
    if not configured():
        state.update(ok=False, error="non configuré")
        return state
    try:
        async with httpx.AsyncClient(timeout=10, verify=VERIFY) as client:
            res = await _get(client, "/cluster/resources") or []
            nodes, guests, storages = [], [], []
            for r in res:
                if r.get("type") == "node":
                    n = {"name": r.get("node"), "status": r.get("status"), "cpu": round(100 * (r.get("cpu") or 0), 1),
                         "mem": _pct(r.get("mem", 0), r.get("maxmem", 0)), "mem_used": r.get("mem", 0), "mem_total": r.get("maxmem", 0),
                         "disk": _pct(r.get("disk", 0), r.get("maxdisk", 0)), "uptime": r.get("uptime", 0), "cores": r.get("maxcpu")}
                    if n["status"] == "online":
                        try:
                            st = await _get(client, f"/nodes/{n['name']}/status") or {}
                            n["load"] = st.get("loadavg")
                            n["model"] = (st.get("cpuinfo") or {}).get("model")
                            n["pve"] = st.get("pveversion")
                        except (httpx.HTTPError, RuntimeError):
                            pass
                    nodes.append(n)
                elif r.get("type") in ("qemu", "lxc"):
                    guests.append({"id": r.get("vmid"), "name": r.get("name") or str(r.get("vmid")), "type": "VM" if r["type"] == "qemu" else "LXC",
                                   "node": r.get("node"), "status": r.get("status"), "cpu": round(100 * (r.get("cpu") or 0), 1),
                                   "cores": r.get("maxcpu"), "mem": _pct(r.get("mem", 0), r.get("maxmem", 0)), "mem_used": r.get("mem", 0),
                                   "mem_total": r.get("maxmem", 0), "uptime": r.get("uptime", 0), "template": bool(r.get("template"))})
                elif r.get("type") == "storage" and r.get("status") == "available":
                    storages.append({"name": r.get("storage"), "node": r.get("node"), "used": r.get("disk", 0), "total": r.get("maxdisk", 0),
                                     "pct": _pct(r.get("disk", 0), r.get("maxdisk", 0)), "kind": r.get("plugintype")})
        guests = [g for g in guests if not g["template"]]
        guests.sort(key=lambda g: (g["status"] != "running", g["id"]))
        state.update(ok=True, error="", updated=time.time(), nodes=nodes, guests=guests, storages=storages)
        _fails = 0
        now = time.time()
        for n in nodes:
            h = history.setdefault(n["name"], deque(maxlen=24 * 60))
            h.append((round(now), n["cpu"], n["mem"]))
    except (httpx.HTTPError, RuntimeError, ValueError) as e:
        _fails += 1
        msg = str(e) if isinstance(e, RuntimeError) else f"injoignable ({e.__class__.__name__})"
        state.update(ok=False, error=msg, updated=time.time())
    return state


# ---------------------------------------------------------------- alertes


async def _notify(title: str, body: str) -> None:
    if not settings()["notify"]:
        return
    try:
        await telegram.broadcast(f"*{title}*\n{body}")
    except Exception:  # noqa: BLE001
        pass
    try:
        await notify.send(title, body, tags="computer")
    except Exception:  # noqa: BLE001
        pass


def _check(key: str, cond: bool, title: str, body: str, sustained: bool, out: list) -> None:
    """Met à jour une alerte : déclenchée si `cond` (pendant N minutes si `sustained`), rétablie sinon."""
    s = settings()
    now = time.time()
    if cond:
        _high_since.setdefault(key, now)
        if (not sustained or now - _high_since[key] >= s["minutes"] * 60) and key not in _active:
            _active[key] = {"key": key, "title": title, "body": body, "since": _high_since[key]}
            if now - _last_sent.get(key, 0) > 3600:
                _last_sent[key] = now
                out.append((f"⚠ {title}", body))
    else:
        _high_since.pop(key, None)
        if key in _active:
            a = _active.pop(key)
            out.append((f"✓ Rétabli : {a['title']}", "La situation est revenue à la normale."))


async def evaluate() -> list[tuple[str, str]]:
    s, out = settings(), []
    if not configured():
        return out
    _check("unreachable", not state["ok"] and _fails >= 3, "Proxmox injoignable", f"Atom n'arrive plus à joindre Proxmox : {state['error']}", False, out)
    if state["ok"]:
        for n in state["nodes"]:
            _check(f"node-down:{n['name']}", n["status"] != "online", f"Nœud {n['name']} hors ligne", "Le nœud ne répond plus au cluster.", False, out)
            _check(f"cpu:{n['name']}", n["cpu"] >= s["cpu"], f"Processeur de {n['name']} à {n['cpu']:.0f} %",
                   f"Au-dessus de {s['cpu']} % depuis {s['minutes']} min.", True, out)
            _check(f"mem:{n['name']}", n["mem"] >= s["mem"], f"Mémoire de {n['name']} à {n['mem']:.0f} %",
                   f"Au-dessus de {s['mem']} % depuis {s['minutes']} min.", True, out)
        for st in state["storages"]:
            _check(f"storage:{st['node']}:{st['name']}", st["pct"] >= s["storage"], f"Stockage {st['name']} plein à {st['pct']:.0f} %",
                   f"Sur {st['node']} : {st['used'] / 1e9:.0f} Go utilisés sur {st['total'] / 1e9:.0f} Go.", False, out)
        if s["guest_down"]:
            for g in state["guests"]:
                k = f"{g['node']}:{g['id']}"
                running = g["status"] == "running"
                was = _was_running.get(k)
                _was_running[k] = running
                # seulement si l'invité tournait avant (un arrêt volontaire déclenche aussi l'alerte, une fois)
                _check(f"guest:{k}", was is not None and (was or f"guest:{k}" in _active) and not running,
                       f"{g['type']} {g['id']} ({g['name']}) arrêtée", f"Statut : {g['status']} sur {g['node']}.", False, out)
    for title, body in out:
        await _notify(title, body)
    return out


async def scheduler() -> None:
    if not configured():
        return
    log.info("surveillance Proxmox : %s, toutes les %d s", URL, INTERVAL)
    while True:
        try:
            await poll()
            await evaluate()
        except Exception:  # noqa: BLE001
            log.exception("surveillance Proxmox")
        await asyncio.sleep(INTERVAL)


def alerts() -> list[dict]:
    return list(_active.values())


# ---------------------------------------------------------------- pour la discussion et Telegram

KEYWORDS = ("serveur", "proxmox", "vm", "conteneur", "lxc", "nœud", "noeud", "stockage", "machine virtuelle", "homelab")


def wants(message: str) -> bool:
    m = message.lower()
    return configured() and any(k in m for k in KEYWORDS)


def _gb(b) -> str:
    return f"{b / 1e9:.1f} Go"


def _dur(sec) -> str:
    d, h = int(sec // 86400), int(sec % 86400 // 3600)
    return f"{d} j {h} h" if d else f"{h} h {int(sec % 3600 // 60)} min"


def summary(markdown: bool = True) -> str:
    if not configured():
        return "La surveillance Proxmox n'est pas configurée."
    if not state["ok"]:
        return f"Proxmox est injoignable : {state['error']}."
    lines = []
    for n in state["nodes"]:
        lines.append(f"Nœud {n['name']} ({n['status']}) : processeur {n['cpu']:.0f} %, mémoire {n['mem']:.0f} % "
                     f"({_gb(n['mem_used'])} / {_gb(n['mem_total'])}), disque système {n['disk']:.0f} %, "
                     f"en marche depuis {_dur(n['uptime'])}" + (f", charge {', '.join(n['load'])}" if n.get("load") else ""))
    run = [g for g in state["guests"] if g["status"] == "running"]
    stop = [g for g in state["guests"] if g["status"] != "running"]
    lines.append(f"Invités : {len(run)} en marche, {len(stop)} arrêtés.")
    for g in run:
        lines.append(f"- {g['type']} {g['id']} {g['name']} : processeur {g['cpu']:.0f} %, mémoire {g['mem']:.0f} % ({_gb(g['mem_used'])})")
    for g in stop:
        lines.append(f"- {g['type']} {g['id']} {g['name']} : {g['status']}")
    for st in state["storages"]:
        lines.append(f"Stockage {st['name']} ({st['node']}) : {st['pct']:.0f} % ({_gb(st['used'])} / {_gb(st['total'])})")
    if _active:
        lines.append("Alertes en cours : " + " ; ".join(a["title"] for a in _active.values()))
    return "\n".join(lines)


def prompt_block() -> str:
    age = int(time.time() - state["updated"]) if state["updated"] else None
    return ("État actuel du serveur Proxmox de l'utilisateur (relevé il y a " + (f"{age} s" if age is not None else "?") +
            ", lecture seule — tu ne peux rien redémarrer) :\n" + summary() +
            "\nRéponds à partir de ces données : signale ce qui mérite attention et suggère quoi vérifier.")
