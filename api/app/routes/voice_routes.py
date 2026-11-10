"""Routes : voix (dictée et lecture à voix haute)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import voice

router = APIRouter()


@router.get("/api/voice")
def voice_status():
    return voice.status()


@router.post("/api/voice/transcribe")
async def voice_transcribe(request: Request):
    """Corps : l'enregistrement brut (audio/webm, audio/ogg, audio/mp4…), 15 Mo au plus."""
    if int(request.headers.get("content-length") or 0) > voice.MAX_AUDIO:
        raise HTTPException(413, "Enregistrement trop long (15 Mo au plus).")
    audio = await request.body()
    mime = (request.headers.get("content-type") or "audio/webm").split(";")[0].strip()
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav"}.get(mime, "webm")
    try:
        text = await voice.transcribe(audio, f"dictee.{ext}", mime)
    except voice.VoiceError as e:
        raise HTTPException(503, str(e)) from e
    return {"text": text}


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


@router.post("/api/voice/speak")
async def voice_speak(body: SpeakIn):
    try:
        audio, mime = await voice.speak(voice.clean_for_speech(body.text))
    except voice.VoiceError as e:
        raise HTTPException(503, str(e)) from e
    return Response(audio, media_type=mime)
