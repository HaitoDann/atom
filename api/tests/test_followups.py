"""Relances des rappels : boutons, confirmation, report, relance après délai, heures calmes, brief."""

import asyncio
import time
from datetime import datetime

import pytest


def run(coro):
    return asyncio.run(coro)


def _sent(text="Arroser les plantes", minutes_ago=90):
    """Un rappel déjà envoyé il y a `minutes_ago` minutes, sans confirmation."""
    from app import db
    rid = db.add_reminder(None, text, time.time() - minutes_ago * 60)
    db.mark_reminder(rid, "sent")
    with db.conn() as c:
        c.execute("UPDATE reminders SET sent_at = ? WHERE id = ?", (time.time() - minutes_ago * 60, rid))
    return rid


@pytest.mark.parametrize("now,expected", [("23:00", True), ("03:00", True), ("07:29", True), ("07:30", False), ("14:00", False)])
def test_quiet_hours(now, expected):
    from app import reminders
    s = {**reminders.FOLLOWUP_DEFAULTS, "quiet_start": "22:00", "quiet_end": "07:30"}
    assert reminders.quiet(datetime.strptime(f"2026-11-09 {now}", "%Y-%m-%d %H:%M"), s) is expected


def test_fire_sends_buttons(client, monkeypatch):
    from app import db, notify, reminders
    got = []

    async def fake(title, body, cid=None, tags="", buttons=None):
        got.append(buttons)
        return True
    monkeypatch.setattr(notify, "send", fake)
    rid = db.add_reminder(None, "Sortir les poubelles", time.time() - 1)
    run(reminders.fire(db.get_reminder(rid)))
    data = [d for row in got[0] for _, d in row]
    assert data == [f"rem:done:{rid}", f"rem:snooze:{rid}:60", f"rem:tomorrow:{rid}"]
    assert db.get_reminder(rid)["status"] == "sent"


def test_followup_due_then_capped(client):
    from app import db, reminders
    rid = _sent(minutes_ago=90)
    fresh = _sent("Tout juste envoyé", minutes_ago=10)
    s = {**reminders.FOLLOWUP_DEFAULTS, "delay": 60, "max": 2, "quiet_start": "00:00", "quiet_end": "00:00"}
    day = datetime.strptime("2026-11-09 14:00", "%Y-%m-%d %H:%M")
    due = {r["id"] for r in reminders.followups_due(time.time(), day, s)}
    assert rid in due and fresh not in due
    db.nudge_reminder(rid)                                              # 1re relance à l'instant : pas de 2e tout de suite
    assert rid not in {r["id"] for r in reminders.followups_due(time.time(), day, s)}
    assert rid in {r["id"] for r in reminders.followups_due(time.time() + 3601, day, s)}
    db.nudge_reminder(rid)                                              # plafond atteint (max 2)
    assert rid not in {r["id"] for r in reminders.followups_due(time.time() + 10_000, day, s)}
    assert reminders.followups_due(time.time(), day, {**s, "enabled": False}) == []


def test_done_and_snooze_via_api(client):
    from app import db
    rid = _sent("Payer la facture")
    assert any(r["id"] == rid for r in client.get("/api/reminders/unacked").json()["reminders"])
    r = client.post(f"/api/reminders/{rid}/done").json()
    assert r["ok"] and "fait" in r["message"]
    assert db.get_reminder(rid)["status"] == "done"
    assert client.post(f"/api/reminders/{rid}/done").status_code == 409             # déjà traité
    assert not any(x["id"] == rid for x in client.get("/api/reminders/unacked").json()["reminders"])

    rid2 = _sent("Rappeler Paul")
    r = client.post(f"/api/reminders/{rid2}/snooze", json={"minutes": 60}).json()
    new = db.get_reminder(r["new_id"])
    assert new["status"] == "pending" and new["text"] == "Rappeler Paul" and 3500 < new["due_at"] - time.time() < 3700
    assert db.get_reminder(rid2)["status"] == "snoozed"
    r = client.post(f"/api/reminders/{r['new_id']}/snooze", json={"tomorrow": True}).json()   # report d'un rappel pas encore parti
    assert "demain à 09h00" in r["message"]


def test_followup_settings(client):
    r = client.put("/api/reminders/followups", json={"delay": 30, "max": 3, "quiet_start": "21:30"}).json()
    assert r["delay"] == 30 and r["max"] == 3 and r["quiet_start"] == "21:30"
    assert client.put("/api/reminders/followups", json={"delay": 1}).status_code == 422


def test_telegram_button(client, monkeypatch):
    from app import db, telegram
    calls = []

    async def fake_call(client_, method, **kw):
        calls.append((method, kw))
        return {}
    monkeypatch.setattr(telegram, "call", fake_call)

    async def fake_send(client_, chat_id, text, **extra):
        calls.append(("sendMessage", {"text": text}))
    monkeypatch.setattr(telegram, "send_text", fake_send)
    rid = _sent("Prendre les médicaments")
    cq = {"id": "1", "data": f"rem:done:{rid}", "message": {"chat": {"id": 5}, "message_id": 9}}
    run(telegram.reminder_button(None, cq))
    methods = [m for m, _ in calls]
    assert methods == ["answerCallbackQuery", "editMessageReplyMarkup", "sendMessage"]
    assert db.get_reminder(rid)["status"] == "done"


def test_brief_lists_unconfirmed(client):
    from app import brief
    _sent("Envoyer le dossier", minutes_ago=180)
    assert "Pas encore fait : Envoyer le dossier" in brief.section_reminders()
