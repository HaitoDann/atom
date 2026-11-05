"""Le lien avec Atom : il grandit avec le temps passé ensemble, sans jamais se dégrader.

Rien ne baisse si tu t'absentes : pas de faim, pas de punition. Chaque moment partagé
(messages, souvenirs, caresses, nourriture — fichiers et recherches) fait grandir le lien.
"""

from __future__ import annotations

import time
from contextlib import closing

from . import db

STAGES = [
    (0, "Éveil", "Atom vient de naître. Il découvre le monde à travers toi."),
    (60, "Curieux", "Il pose ses premières questions sur toi."),
    (180, "Familier", "Il reconnaît ta façon de parler."),
    (450, "Complice", "Vous avez vos habitudes, vos sujets."),
    (1000, "Attaché", "Il pense à toi entre deux conversations."),
    (2200, "Inséparable", "Un lien solide, construit jour après jour."),
]


def _count(sql: str) -> int:
    with db.conn() as c:
        return int(c.execute(sql).fetchone()[0] or 0)


def bump(key: str, n: int = 1) -> int:
    v = int(db.kv_get(f"companion:{key}", "0") or 0) + n
    db.kv_set(f"companion:{key}", str(v))
    return v


def state() -> dict:
    born = db.kv_get("companion:born")
    if not born:
        first = _count("SELECT MIN(created_at) FROM messages") or int(time.time())
        born = str(int(first))
        db.kv_set("companion:born", born)
    born_at = float(born)
    days = max(0, int((time.time() - born_at) // 86400))
    messages = _count("SELECT COUNT(*) FROM messages WHERE role = 'user'")
    conversations = _count("SELECT COUNT(*) FROM conversations")
    memories = _count("SELECT COUNT(*) FROM memories")
    pets = int(db.kv_get("companion:pets", "0") or 0)
    fed = int(db.kv_get("companion:fed", "0") or 0)
    points = messages * 2 + memories * 6 + pets * 2 + fed * 4 + days * 5 + conversations * 3
    level = 0
    for i, (need, _, _) in enumerate(STAGES):
        if points >= need:
            level = i
    cur_need = STAGES[level][0]
    next_need = STAGES[level + 1][0] if level + 1 < len(STAGES) else None
    progress = 1.0 if next_need is None else (points - cur_need) / (next_need - cur_need)
    return {
        "born_at": born_at, "days": days, "messages": messages, "conversations": conversations,
        "memories": memories, "pets": pets, "fed": fed, "points": points,
        "level": level, "stage": STAGES[level][1], "stage_text": STAGES[level][2],
        "next_stage": STAGES[level + 1][1] if next_need else None,
        "progress": round(max(0.0, min(1.0, progress)), 3),
    }
