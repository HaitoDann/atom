"""Brief du matin : réglages, moment d'envoi, contenu, envoi et conversation dédiée."""

import asyncio
from datetime import datetime

import pytest


def test_settings_validation(client):
    r = client.put("/api/brief", json={"time": "7:05", "days": [0, 2, 9], "city": "  Lyon ", "sections": {"news": False}}).json()
    assert r["time"] == "07:05" and r["days"] == [0, 2] and r["city"] == "Lyon"
    assert r["sections"]["news"] is False and r["sections"]["reminders"] is True
    assert client.put("/api/brief", json={"time": "midi"}).status_code == 422
    assert set(r["names"]) == {"agenda", "reminders", "weather", "server", "providers", "news", "memories"}


@pytest.mark.parametrize("now,last,expected", [
    ("2026-11-09 07:29", None, False),          # trop tôt
    ("2026-11-09 07:30", None, True),           # à l'heure
    ("2026-11-09 09:00", None, True),           # Atom démarré en retard : envoyé quand même
    ("2026-11-09 12:00", None, False),          # plus de 4 h après : on laisse tomber
    ("2026-11-09 08:00", "2026-11-09", False),  # déjà envoyé aujourd'hui
    ("2026-11-14 08:00", None, False),          # samedi non coché
])
def test_due(now, last, expected):
    from app import brief
    s = {**brief.DEFAULTS, "enabled": True, "time": "07:30", "days": [0, 1, 2, 3, 4]}
    assert brief.due(s, datetime.strptime(now, "%Y-%m-%d %H:%M"), last) is expected
    assert brief.due({**s, "enabled": False}, datetime.strptime("2026-11-09 08:00", "%Y-%m-%d %H:%M"), None) is False


def test_reminders_today_only(client):
    import time

    from app import brief, db
    from app.reminders import now_local
    end_of_day = now_local().replace(hour=23, minute=59).timestamp()
    db.add_reminder(None, "Appeler le garage", min(time.time() + 60, end_of_day - 1))
    db.add_reminder(None, "Rappel lointain", time.time() + 5 * 86400)
    out = brief.section_reminders()
    assert "Appeler le garage" in out and "lointain" not in out


def test_preview_and_send(client, monkeypatch):
    from app import brief, notify
    sent = []

    async def fake_send(title, body, cid=None, tags=""):
        sent.append((title, body))
        return True
    monkeypatch.setattr(notify, "send", fake_send)
    client.put("/api/brief", json={"city": "Lyon", "intro": True,
                                   "sections": {"weather": True, "reminders": True, "server": True, "providers": True}})
    p = client.post("/api/brief/preview").json()
    assert p["title"].startswith("☀️ Brief du") and "Météo" in p["text"] and "Lyon" in p["text"]
    assert p["intro"] and not sent                                       # l'aperçu n'envoie rien
    r = client.post("/api/brief/send").json()
    assert r["sent"] and len(sent) == 1 and sent[0][0] == r["title"]
    msgs = client.get(f"/api/conversations/{r['conversation_id']}/messages").json()["messages"]
    assert msgs[-1]["content"].startswith("**☀️ Brief du")
    assert client.post("/api/brief/send").json()["conversation_id"] == r["conversation_id"]   # même conversation
    assert client.get("/api/brief").json()["last"]["sent"] is True
    assert brief.last()["date"]


def test_failing_section_does_not_break_brief(client, monkeypatch):
    from app import brief

    async def boom(city):
        raise RuntimeError("météo en panne")
    monkeypatch.setattr(brief, "section_weather", boom)
    b = asyncio.run(brief.build({**brief.settings(), "intro": False, "city": "Lyon"}))
    assert "indisponible" in b["sections"]["weather"]


def test_providers_section_flags_broken_model(monkeypatch):
    from app import brief, providers

    class P:
        def __init__(self, i, n):
            self.id, self.name, self.configured = i, n, True

    monkeypatch.setattr(providers, "ALL", [P("groq", "Groq"), P("gemini", "Gemini")])
    monkeypatch.setattr(providers, "model_of", lambda p: "m")

    async def ping(p):
        return "modèle introuvable" if p.id == "gemini" else ""
    monkeypatch.setattr(providers, "ping", ping)
    out = asyncio.run(brief.section_providers())
    assert "1/2" in out and "Gemini" in out and "Réglages → Hybride" in out and "Groq" not in out
