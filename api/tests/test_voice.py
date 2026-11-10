"""Voix : transcription (serveur compatible OpenAI, téléchargement du modèle), lecture, messages vocaux Telegram."""

import asyncio

import httpx
import pytest


def run(coro):
    return asyncio.run(coro)


def test_status_and_mock_transcribe(client):
    st = client.get("/api/voice").json()
    assert st["stt"] is True and st["tts_server"] is False          # mode test : transcription simulée
    r = client.post("/api/voice/transcribe", content=b"\x1a\x45\xdf\xa3fake", headers={"Content-Type": "audio/webm"})
    assert r.status_code == 200 and "dictée de test" in r.json()["text"]
    assert client.post("/api/voice/transcribe", content=b"", headers={"Content-Type": "audio/webm"}).status_code == 503
    assert client.post("/api/voice/speak", json={"text": "Bonjour"}).status_code == 503   # lecture : par le navigateur


def test_transcribe_downloads_missing_model(monkeypatch):
    """Speaches répond 404 « model not found » : Atom demande le téléchargement puis réessaie."""
    from app import voice
    seen = []

    def handler(req: httpx.Request):
        seen.append((req.method, req.url.path))
        if req.url.path == "/v1/audio/transcriptions":
            if not any(p.startswith("/v1/models/") for _, p in seen):
                return httpx.Response(404, json={"detail": "Model 'Systran/faster-whisper-small' not found"})
            assert b"name=\"language\"" in req.content and b"fr" in req.content
            return httpx.Response(200, json={"text": "  Rappelle-moi   demain  "})
        return httpx.Response(200, json={})
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: real(*a, transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(voice, "PROVIDER", "ollama")
    monkeypatch.setattr(voice, "STT_URL", "http://speaches:8000")
    assert run(voice.transcribe(b"son", "d.webm", "audio/webm")) == "Rappelle-moi demain"
    assert [p for _, p in seen] == ["/v1/audio/transcriptions", "/v1/models/Systran/faster-whisper-small",
                                    "/v1/audio/transcriptions"]


def test_transcribe_not_configured(monkeypatch):
    from app import voice
    monkeypatch.setattr(voice, "PROVIDER", "ollama")
    monkeypatch.setattr(voice, "STT_URL", "")
    with pytest.raises(voice.VoiceError, match="non configurée"):
        run(voice.transcribe(b"son"))
    with pytest.raises(voice.VoiceError, match="trop long"):
        run(voice.transcribe(b"x" * (voice.MAX_AUDIO + 1)))


def test_speak_with_server(client, monkeypatch):
    from app import voice

    def handler(req: httpx.Request):
        import json
        body = json.loads(req.content)
        assert body["voice"] == "siwis" and "```" not in body["input"] and "**" not in body["input"]
        return httpx.Response(200, content=b"ID3mp3", headers={"content-type": "audio/mpeg"})
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: real(*a, transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(voice, "TTS_URL", "http://tts:8000")
    monkeypatch.setattr(voice, "TTS_VOICE", "siwis")
    r = client.post("/api/voice/speak", json={"text": "**Bonjour** !\n```py\nx=1\n```\nVoir [la doc](http://x) [1]"})
    assert r.status_code == 200 and r.content == b"ID3mp3" and r.headers["content-type"] == "audio/mpeg"


def test_clean_for_speech():
    from app import voice
    t = voice.clean_for_speech("# Titre\n**gras** et [lien](http://a) [2]\n| a | b |\n```\ncode\n```")
    assert t == "Titre gras et lien (bloc de code)"


def test_telegram_voice_message(client, monkeypatch):
    from app import telegram, voice
    sent = []

    async def fake_call(c, method, **kw):
        assert method == "getFile"
        return {"file_path": "voice/f.oga"}

    async def fake_send(c, chat_id, text, **kw):
        sent.append(text)

    class C:
        async def get(self, url):
            assert url.endswith("/voice/f.oga")
            return httpx.Response(200, content=b"ogg", request=httpx.Request("GET", url))
    monkeypatch.setattr(telegram, "call", fake_call)
    monkeypatch.setattr(telegram, "send_text", fake_send)
    text = run(telegram.transcribe_voice(C(), 1, {"file_id": "abc", "mime_type": "audio/ogg"}))
    assert text.startswith("Bonjour Atom") and sent and sent[0].startswith("🎤 _Bonjour Atom")
    monkeypatch.setattr(voice, "status", lambda: {"stt": False})
    assert run(telegram.transcribe_voice(C(), 1, {"file_id": "abc"})) == "" and "pas activés" in sent[-1]
