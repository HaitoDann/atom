"""Voix : dictée (transcription) et lecture à voix haute, en local.

- Transcription : un serveur compatible OpenAI (/v1/audio/transcriptions), par défaut Speaches (faster-whisper)
  lancé par docker-compose.voice.yml. ATOM_STT_URL, ATOM_STT_MODEL (Systran/faster-whisper-small par défaut).
  Si le modèle n'est pas encore installé sur le serveur, Atom demande son téléchargement puis réessaie.
- Lecture : par défaut dans le navigateur (synthèse vocale du système, locale et sans réglage). Optionnel :
  un serveur compatible OpenAI (/v1/audio/speech) via ATOM_TTS_URL, ATOM_TTS_MODEL et ATOM_TTS_VOICE.
- Telegram : les messages vocaux sont transcrits puis traités comme du texte.
Aucun son n'est envoyé à un service extérieur : tout passe par tes serveurs.
"""

from __future__ import annotations

import logging
import os

import httpx

from .config import PROVIDER

log = logging.getLogger("atom.voice")

STT_URL = os.getenv("ATOM_STT_URL", "").rstrip("/")
STT_MODEL = os.getenv("ATOM_STT_MODEL", "Systran/faster-whisper-small")
STT_LANG = os.getenv("ATOM_STT_LANGUAGE", "fr")
TTS_URL = os.getenv("ATOM_TTS_URL", "").rstrip("/")
TTS_MODEL = os.getenv("ATOM_TTS_MODEL", "")
TTS_VOICE = os.getenv("ATOM_TTS_VOICE", "")
MAX_AUDIO = 15 * 1024 * 1024          # 15 Mo : quelques minutes de parole


class VoiceError(RuntimeError):
    pass


def status() -> dict:
    return {"stt": bool(STT_URL) or PROVIDER == "mock", "stt_model": STT_MODEL if STT_URL else "",
            "tts_server": bool(TTS_URL), "language": STT_LANG}


async def transcribe(audio: bytes, filename: str = "audio.webm", mime: str = "audio/webm") -> str:
    """Texte dicté. Lève VoiceError si la transcription n'est pas configurée ou échoue."""
    if not audio:
        raise VoiceError("enregistrement vide")
    if len(audio) > MAX_AUDIO:
        raise VoiceError("enregistrement trop long (15 Mo au plus)")
    if PROVIDER == "mock":
        return "Bonjour Atom, ceci est une dictée de test."
    if not STT_URL:
        raise VoiceError("transcription non configurée (ATOM_STT_URL, voir README → Voix)")
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=300)) as c:
        for attempt in range(2):
            r = await c.post(f"{STT_URL}/v1/audio/transcriptions",
                             files={"file": (filename, audio, mime)},
                             data={"model": STT_MODEL, "language": STT_LANG, "response_format": "json"})
            if r.status_code == 404 and attempt == 0 and "model" in r.text.lower():
                # Modèle pas encore installé sur le serveur Speaches : téléchargement, puis nouvel essai.
                log.info("voix : téléchargement du modèle %s", STT_MODEL)
                await c.post(f"{STT_URL}/v1/models/{STT_MODEL}", timeout=httpx.Timeout(10, read=900))
                continue
            if r.status_code != 200:
                raise VoiceError(f"le serveur de transcription a répondu {r.status_code} : {r.text[:160]}")
            break
    try:
        text = r.json().get("text", "")
    except ValueError:
        text = r.text
    return " ".join(text.split()).strip()


async def speak(text: str) -> tuple[bytes, str]:
    """Audio (mp3) du texte via le serveur de synthèse ; VoiceError s'il n'y en a pas (le navigateur lit alors)."""
    if not TTS_URL:
        raise VoiceError("synthèse vocale côté serveur non configurée (le navigateur lit la réponse)")
    body = {"input": text[:4000], "response_format": "mp3"}
    if TTS_MODEL:
        body["model"] = TTS_MODEL
    if TTS_VOICE:
        body["voice"] = TTS_VOICE
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=180)) as c:
        r = await c.post(f"{TTS_URL}/v1/audio/speech", json=body)
    if r.status_code != 200:
        raise VoiceError(f"le serveur de synthèse a répondu {r.status_code} : {r.text[:160]}")
    return r.content, r.headers.get("content-type", "audio/mpeg")


def clean_for_speech(md: str) -> str:
    """Texte à lire : sans blocs de code, liens, tableaux ni balises Markdown."""
    import re
    t = re.sub(r"```[\s\S]*?```", " (bloc de code) ", md or "")
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^\s*\|.*\|\s*$", "", t, flags=re.M)
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"\[\d+\]", "", t)
    return " ".join(t.split())
