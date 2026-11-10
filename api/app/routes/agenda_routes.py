"""Routes : agenda d'Atom et flux d'abonnement .ics."""
from __future__ import annotations

import hmac
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import agenda

router = APIRouter()


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start: str = Field(description="AAAA-MM-JJTHH:MM (heure locale) ou AAAA-MM-JJ (journée entière)")
    minutes: int | None = Field(default=60, ge=5, le=14 * 24 * 60)
    location: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)
    repeat: str = Field(default="", pattern="^(|daily|weekly|monthly|yearly)$")
    repeat_interval: int = Field(default=1, ge=1, le=99)
    repeat_until: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    remind_min: int | None = Field(default=30, ge=0, le=7 * 24 * 60)


def _fields(body: EventIn) -> dict:
    when = agenda.parse_when(body.start)
    if not when:
        raise HTTPException(400, f"Date illisible : {body.start}")
    start, all_day = when
    until = agenda.parse_when(body.repeat_until + "T23:59")[0] if body.repeat_until else None
    return dict(title=body.title, start_at=start, end_at=start + (body.minutes or 60) * 60, all_day=all_day,
                location=body.location, notes=body.notes, repeat=body.repeat, repeat_interval=body.repeat_interval,
                repeat_until=until, remind_min=body.remind_min)


@router.get("/api/agenda")
def get_agenda(days: int = 30, past: int = 0, start: str | None = None, end: str | None = None):
    """Occurrences des `days` prochains jours (et des `past` derniers), ou de la période [start, end[ (AAAA-MM-JJ)."""
    now = time.time()
    if start and end:
        a, b = agenda.parse_when(start), agenda.parse_when(end)
        if not a or not b or b[0] <= a[0] or b[0] - a[0] > 400 * 86400:
            raise HTTPException(400, "Période invalide")
        lo, hi = a[0], b[0]
    else:
        days, past = max(1, min(400, days)), max(0, min(400, past))
        lo, hi = now - past * 86400, now + days * 86400
    from ..config import TIMEZONE
    return {"occurrences": agenda.between(lo, hi), "events": len(agenda.all_events()), "timezone": TIMEZONE,
            "today": agenda.now_local().strftime("%Y-%m-%d")}


@router.get("/api/agenda/{eid:int}")
def get_event(eid: int):
    ev = agenda.get(eid)
    if not ev:
        raise HTTPException(404, "Rendez-vous introuvable")
    return ev


@router.post("/api/agenda")
def post_event(body: EventIn):
    f = _fields(body)
    return agenda.create(**f)


@router.put("/api/agenda/{eid:int}")
def put_event(eid: int, body: EventIn):
    if not agenda.get(eid):
        raise HTTPException(404, "Rendez-vous introuvable")
    f = _fields(body)
    if f["all_day"]:                                    # journée entière : au moins jusqu'au lendemain
        f["end_at"] = max(f["end_at"], f["start_at"] + 86400)
    return agenda.update(eid, **{**f, "all_day": int(f["all_day"])})


@router.delete("/api/agenda/{eid:int}")
def delete_event(eid: int, occurrence: float | None = None):
    """occurrence : début (timestamp) d'une seule occurrence à retirer d'un événement récurrent."""
    if not agenda.delete(eid, occurrence):
        raise HTTPException(404, "Rendez-vous introuvable")
    return {"ok": True}


@router.get("/api/agenda/feed")
def feed_info(request: Request):
    t = agenda.feed_token()
    return {"path": f"/agenda/{t}.ics", "url": str(request.base_url).rstrip("/") + f"/agenda/{t}.ics"}


@router.post("/api/agenda/feed/regenerate")
def feed_regenerate(request: Request):
    """Nouveau lien : l'ancien cesse de fonctionner (si tu l'as partagé par erreur)."""
    agenda.feed_token(regenerate=True)
    return feed_info(request)


@router.get("/agenda/{token}.ics")
def feed(token: str):
    """Flux d'abonnement (lecture seule), protégé par son jeton : pas de session nécessaire (appli d'agenda)."""
    if not hmac.compare_digest(token, agenda.feed_token()):
        raise HTTPException(404, "Introuvable")
    return Response(agenda.ics(), media_type="text/calendar; charset=utf-8",
                    headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="atom.ics"'})
