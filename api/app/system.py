"""Infos système affichées dans le panneau de l'entité (CPU, RAM, uptime, modèle chargé).

Lu dans /proc : dans un conteneur LXC/Docker, ce sont les valeurs vues par le conteneur.
"""

from __future__ import annotations

import os
import time

import httpx

from .config import OLLAMA_URL, PROVIDER

_last_cpu: tuple[float, float] | None = None  # (total, idle)


def _cpu_times() -> tuple[float, float] | None:
    try:
        with open("/proc/stat") as f:
            parts = [float(x) for x in f.readline().split()[1:]]
    except (OSError, ValueError):
        return None
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
    return sum(parts), idle


def cpu_percent() -> float | None:
    global _last_cpu
    now = _cpu_times()
    if now is None:
        return None
    prev, _last_cpu = _last_cpu, now
    if prev is None:
        time.sleep(0.15)
        return cpu_percent()
    dt, di = now[0] - prev[0], now[1] - prev[1]
    return round(100 * (1 - di / dt), 1) if dt > 0 else 0.0


def memory() -> dict | None:
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
    except (OSError, ValueError):
        return None
    total = info.get("MemTotal")
    avail = info.get("MemAvailable", info.get("MemFree"))
    if not total or avail is None:
        return None
    return {"total": total, "used": total - avail}


def uptime() -> float | None:
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError):
        return None


async def loaded_models() -> list[dict]:
    if PROVIDER == "mock":
        return [{"name": "mock", "size": 0}]
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{OLLAMA_URL}/api/ps")
        return [{"name": m["name"], "size": m.get("size", 0)} for m in r.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return []


async def snapshot() -> dict:
    return {
        "cpu": cpu_percent(),
        "cores": os.cpu_count(),
        "memory": memory(),
        "uptime": uptime(),
        "loaded": await loaded_models(),
    }
