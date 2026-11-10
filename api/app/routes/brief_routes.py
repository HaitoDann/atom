"""Routes : brief du matin."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import brief

router = APIRouter()


class Sections(BaseModel):
    agenda: bool | None = None
    reminders: bool | None = None
    weather: bool | None = None
    server: bool | None = None
    providers: bool | None = None
    news: bool | None = None
    memories: bool | None = None


class BriefIn(BaseModel):
    enabled: bool | None = None
    time: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    days: list[int] | None = Field(default=None, max_length=7)
    city: str | None = Field(default=None, max_length=80)
    news: str | None = Field(default=None, max_length=200)
    sections: Sections | None = None
    intro: bool | None = None


@router.get("/api/brief")
def get_brief():
    from .. import notify
    return {**brief.settings(), "last": brief.last(), "channels": notify.enabled(), "names": brief.SECTION_NAMES}


@router.put("/api/brief")
def put_brief(body: BriefIn):
    data = body.model_dump(exclude_none=True)
    if body.sections:
        data["sections"] = body.sections.model_dump(exclude_none=True)
    brief.save_settings(data)
    return get_brief()


@router.post("/api/brief/preview")
async def preview_brief():
    """Le brief tel qu'il serait envoyé maintenant, sans l'envoyer."""
    return await brief.build()


@router.post("/api/brief/send")
async def send_brief():
    """Envoie le brief tout de suite (test), sans attendre l'heure prévue."""
    return await brief.send()
