"""Entretien de la mémoire : doublons, contradictions, temporaires, anecdotes, simulation, Garder / Oublier."""

import asyncio
import time
from datetime import datetime

import numpy as np
import pytest


def run(coro):
    return asyncio.run(coro)


def vec(*xs):
    v = np.zeros(64, dtype=np.float32)
    for i, x in enumerate(xs):
        v[i] = x
    return v / np.linalg.norm(v)


@pytest.fixture
def mem(client):
    from app import db
    db.clear_memories()
    yield db
    db.clear_memories()


def add(db, text, v, importance=2, created=None, review_at=None, hits=0):
    mid = db.add_memory(text, "auto", v, "semantique", importance, 0.8, review_at)
    f = {"hits": hits}
    if created:
        f["created_at"] = created
    db.set_memory_fields(mid, **f)
    return mid


def active(db):
    return {m["content"] for m in db.list_memories()}


def test_duplicates_merged_keeping_most_important(mem):
    from app import memory_care
    add(mem, "L'utilisateur a un chien nommé Rex", vec(1, 0.01), importance=3)
    add(mem, "L'utilisateur possède un chien, Rex", vec(1, 0.02), importance=1)
    rep = run(memory_care.run())
    assert active(mem) == {"L'utilisateur a un chien nommé Rex"} and len(rep["merged"]) == 1
    archived = [m for m in mem.list_memories(active_only=False) if m.get("archived_at")]
    assert archived and archived[0]["superseded_by"]                       # restaurable, avec son remplaçant


def test_contradiction_newer_wins(mem, monkeypatch):
    from app import memory, memory_care
    add(mem, "L'utilisateur habite à Lyon", vec(1, 0.5), created=time.time() - 400 * 86400)
    add(mem, "L'utilisateur habite à Nantes", vec(1, -0.1))

    async def judge(old, new, model):
        return {"relation": "contradiction", "fusion": new}
    monkeypatch.setattr(memory, "_judge", judge)
    rep = run(memory_care.run())
    assert active(mem) == {"L'utilisateur habite à Nantes"}
    assert rep["contradictions"] == [{"old": "L'utilisateur habite à Lyon", "new": "L'utilisateur habite à Nantes"}]


def test_complement_fused(mem, monkeypatch):
    from app import memory, memory_care
    add(mem, "L'utilisateur code en Go", vec(1, 0.5))
    add(mem, "L'utilisateur écrit des tests pour son code Go", vec(1, -0.1))

    async def judge(old, new, model):
        return {"relation": "complement", "fusion": "L'utilisateur code en Go, avec des tests"}
    monkeypatch.setattr(memory, "_judge", judge)
    run(memory_care.run())
    assert active(mem) == {"L'utilisateur code en Go, avec des tests"}


def test_temporary_review_expiry_and_stale(mem):
    from app import memory_care
    now = time.time()
    due = add(mem, "L'utilisateur prépare un examen", vec(0, 1), review_at=now - 86400)
    add(mem, "L'utilisateur était malade", vec(0, 0, 1), review_at=now - 40 * 86400)
    add(mem, "L'utilisateur a vu un film", vec(0, 0, 0, 1), importance=1, created=now - 400 * 86400)
    add(mem, "L'utilisateur aime le jazz", vec(0, 0, 0, 0, 1), importance=1, created=now - 400 * 86400, hits=3)
    rep = run(memory_care.run())
    assert [x["id"] for x in rep["to_review"]] == [due]
    assert rep["expired"] == ["L'utilisateur était malade"] and rep["stale"] == ["L'utilisateur a vu un film"]
    assert active(mem) == {"L'utilisateur prépare un examen", "L'utilisateur aime le jazz"}   # utilisé : gardé


def test_dry_run_changes_nothing(mem):
    from app import memory_care
    add(mem, "Doublon A", vec(1, 0.01))
    add(mem, "Doublon B", vec(1, 0.02))
    rep = run(memory_care.run(dry=True))
    assert rep["dry"] and len(rep["merged"]) == 1 and active(mem) == {"Doublon A", "Doublon B"}


def test_keep_forget_api_and_summary(client, mem, monkeypatch):
    from app import notify
    now = time.time()
    a = add(mem, "L'utilisateur est en vacances", vec(0, 1), review_at=now - 3600)
    b = add(mem, "L'utilisateur cherche un appartement", vec(0, 0, 1), review_at=now - 3600)
    st = client.get("/api/memory/care").json()
    assert {x["id"] for x in st["to_review"]} == {a, b}
    assert client.post(f"/api/memories/{a}/keep").json()["ok"]
    assert client.post(f"/api/memories/{b}/forget").json()["ok"]
    assert client.post(f"/api/memories/{b}/forget").status_code == 404
    assert active(mem) == {"L'utilisateur est en vacances"}
    assert client.get("/api/memory/care").json()["to_review"] == []
    sent = []

    async def fake(title, body, cid=None, tags="", buttons=None):
        sent.append((title, buttons))
        return True
    monkeypatch.setattr(notify, "send", fake)
    add(mem, "L'utilisateur révise son code", vec(0, 0, 0, 1), review_at=now - 3600)
    r = client.post("/api/memory/care/run?notify=true").json()
    assert "Toujours vrai" in r["text"] and "souvenirs actifs" in r["text"]
    assert sent[0][0].startswith("🧠 Ce qu'Atom a retenu") and sent[-1][1][0][0][1].startswith("mem:keep:")


def test_settings_and_schedule(client):
    from app import memory_care
    r = client.put("/api/memory/care", json={"weekday": 2, "time": "9:05", "stale_days": 90}).json()
    assert r["weekday"] == 2 and r["time"] == "09:05" and r["stale_days"] == 90
    s = memory_care.settings()
    wed = datetime.strptime("2026-11-11 09:30", "%Y-%m-%d %H:%M")          # mercredi
    assert memory_care.due(s, wed, None) and not memory_care.due(s, wed, "2026-11-11")
    assert not memory_care.due(s, datetime.strptime("2026-11-12 09:30", "%Y-%m-%d %H:%M"), None)
    client.put("/api/memory/care", json={"weekday": 6, "time": "10:00", "stale_days": 180})


def test_telegram_memory_button(client, mem, monkeypatch):
    from app import telegram
    calls = []

    async def fake_call(c, method, **kw):
        calls.append(method)

    async def fake_send(c, chat_id, text, **kw):
        calls.append("sendMessage")
    monkeypatch.setattr(telegram, "call", fake_call)
    monkeypatch.setattr(telegram, "send_text", fake_send)
    mid = add(mem, "L'utilisateur déménage bientôt", vec(0, 1), review_at=time.time() - 60)
    run(telegram.reminder_button(None, {"id": "1", "data": f"mem:forget:{mid}", "message": {"chat": {"id": 1}, "message_id": 2}}))
    assert calls == ["answerCallbackQuery", "editMessageReplyMarkup", "sendMessage"] and active(mem) == set()
