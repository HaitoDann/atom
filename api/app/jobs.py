"""Tâches de fond suivies (évite qu'elles soient ramassées par le GC)."""

from __future__ import annotations

import asyncio

_jobs: set[asyncio.Task] = set()


def background(coro) -> None:
    t = asyncio.create_task(coro)
    _jobs.add(t)
    t.add_done_callback(_jobs.discard)
