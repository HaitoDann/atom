"""Notifications Web Push : chiffrement aes128gcm (déchiffré comme le ferait le téléphone), VAPID, abonnements, envoi."""

import asyncio
import json
import os
import time

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def run(coro):
    return asyncio.run(coro)


def b64u(b):
    import base64
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s):
    import base64
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hkdf(salt, ikm, info, n):
    h = hmac.HMAC(salt, hashes.SHA256()); h.update(ikm); prk = h.finalize()
    h = hmac.HMAC(prk, hashes.SHA256()); h.update(info + b"\x01")
    return h.finalize()[:n]


class Phone:
    """Côté navigateur, écrit d'après la RFC 8291 (indépendamment de app/push.py) : clés et déchiffrement."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.pub = self.key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.auth = os.urandom(16)

    def sub(self, endpoint="https://push.test/abc"):
        return {"endpoint": endpoint, "keys": {"p256dh": b64u(self.pub), "auth": b64u(self.auth)}}

    def decrypt(self, blob):
        salt, rs, idlen = blob[:16], int.from_bytes(blob[16:20], "big"), blob[20]
        as_pub = blob[21:21 + idlen]
        assert rs == 4096 and idlen == 65
        shared = self.key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
        ikm = hkdf(self.auth, shared, b"WebPush: info\x00" + self.pub + as_pub, 32)
        cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        plain = AESGCM(cek).decrypt(nonce, blob[21 + idlen:], None)
        assert plain.endswith(b"\x02")                         # délimiteur du dernier bloc
        return plain[:-1]


@pytest.fixture
def subs(client):
    from app import db
    with db.conn() as c:
        c.execute("DELETE FROM push_subscriptions")
    yield
    with db.conn() as c:
        c.execute("DELETE FROM push_subscriptions")


def test_encrypt_roundtrip_with_phone_side_decryption(client):
    from app import push
    phone = Phone()
    msg = json.dumps({"title": "📅 Dentiste", "body": "dans 30 min"}, ensure_ascii=False).encode()
    blob = push.encrypt(msg, b64u(phone.pub), b64u(phone.auth))
    assert phone.decrypt(blob) == msg
    assert push.encrypt(msg, b64u(phone.pub), b64u(phone.auth)) != blob            # clé éphémère et sel à chaque envoi


def test_vapid_header_is_a_valid_es256_jwt(client):
    from app import push
    h = push.vapid_header("https://fcm.googleapis.com/fcm/send/xyz", now=1_800_000_000)
    t = h.split("t=")[1].split(",")[0]
    k = h.split("k=")[1]
    head, body, sig = t.split(".")
    raw = unb64u(sig)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64u(k)).verify(der, f"{head}.{body}".encode(),
                                                                                  ec.ECDSA(hashes.SHA256()))
    claims = json.loads(unb64u(body))
    assert claims["aud"] == "https://fcm.googleapis.com" and claims["exp"] == 1_800_000_000 + 12 * 3600
    assert claims["sub"].startswith(("mailto:", "https:")) and k == push.public_key()   # clé stable


def test_subscribe_validation(client, subs):
    phone = Phone()
    assert client.post("/api/push/subscribe", json={"subscription": phone.sub(), "device": "Pixel 8 · appli"}).json()["devices"] == 1
    assert client.post("/api/push/subscribe", json={"subscription": phone.sub()}).json()["devices"] == 1      # même appareil
    assert client.post("/api/push/subscribe", json={"subscription": {**phone.sub(), "endpoint": "http://x/y"}}).status_code == 400
    bad = phone.sub(); bad["keys"]["auth"] = b64u(b"court")
    assert client.post("/api/push/subscribe", json={"subscription": bad}).status_code == 400
    st = client.get("/api/push").json()
    assert len(unb64u(st["public_key"])) == 65 and st["devices"][0]["device"] == "Pixel 8 · appli"


def test_send_encrypts_signs_and_drops_expired(client, subs, monkeypatch):
    from app import push
    good, gone = Phone(), Phone()
    push.subscribe(good.sub("https://push.test/ok"), "Pixel")
    push.subscribe(gone.sub("https://push.test/gone"), "Ancien")
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        return httpx.Response(410 if req.url.path == "/gone" else 201)
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: real(*a, transport=httpx.MockTransport(handler), **kw))
    ok = run(push.send("⏰ Rappel d'Atom", "Arroser les plantes", "/?c=3", "alarm_clock",
                       [[("✅ Fait", "rem:done:7"), ("⏰ +1 h", "rem:snooze:7:60"), ("📅 Demain", "rem:tomorrow:7")]]))
    assert ok and len(seen) == 2
    r = next(x for x in seen if x.url.path == "/ok")
    assert r.headers["content-encoding"] == "aes128gcm" and r.headers["ttl"] == str(24 * 3600)
    assert r.headers["authorization"].startswith("vapid t=") and r.headers["topic"] == "alarmclock"
    data = json.loads(good.decrypt(r.content))
    assert data["title"] == "⏰ Rappel d'Atom" and data["url"] == "/?c=3"
    assert [a["action"] for a in data["actions"]] == ["rem:done:7", "rem:snooze:7:60"]        # 2 boutons au plus
    assert [s["device"] for s in push.subscriptions()] == ["Pixel"]                           # 410 : supprimé


def test_notify_send_includes_push(client, subs, monkeypatch):
    from app import notify, push
    push.subscribe(Phone().sub(), "Pixel")
    got = []

    async def fake(title, body, url="/", tag="", buttons=None):
        got.append((title, url, tag))
        return True
    monkeypatch.setattr(push, "send", fake)
    assert notify.enabled()
    assert run(notify.send("📅 Dentiste", "dans 30 min", tags="calendar"))
    assert got == [("📅 Dentiste", "/?view=agenda", "calendar")]


def test_action_endpoint(client):
    from app import db
    rid = db.add_reminder(None, "Sortir le chien", time.time() - 120)
    db.mark_reminder(rid, "sent")
    r = client.post("/api/push/action", json={"action": f"rem:snooze:{rid}:60"}).json()
    assert r["ok"] and "rappelle" in r["message"]
    assert client.post("/api/push/action", json={"action": "rm -rf"}).status_code == 400
    assert client.post("/api/push/action", json={"action": f"rem:done:{rid}"}).json()["ok"] is False      # déjà reporté


def test_version_in_status(client):
    assert client.get("/api/auth/status").json()["version"]
