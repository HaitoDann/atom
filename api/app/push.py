"""Notifications Web Push (RFC 8030), chiffrées de bout en bout (RFC 8291, aes128gcm) et signées VAPID (RFC 8292).

Aucune dépendance de plus : `cryptography` suffit. Le service de notification du navigateur (sur Android :
celui de Google) ne voit qu'un message chiffré ; seul l'appareil abonné peut le lire.
Les boutons (Fait, +1 h…) sont des « actions » de notification : un toucher appelle /api/push/action depuis le
service worker, avec la session de l'appli.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import db
from .config import PROVIDER

log = logging.getLogger("atom.push")
CONTACT = os.getenv("ATOM_PUSH_CONTACT", "mailto:atom@localhost.localdomain")
TTL = 24 * 3600


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------------------------------------------------------------- clés VAPID (créées une fois, gardées en base)

def _vapid_key() -> ec.EllipticCurvePrivateKey:
    pem = db.kv_get("push_vapid_private")
    if pem:
        return serialization.load_pem_private_key(pem.encode(), password=None)
    key = ec.generate_private_key(ec.SECP256R1())
    db.kv_set("push_vapid_private", key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                      serialization.NoEncryption()).decode())
    return key


def _raw_public(key) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def public_key() -> str:
    """Clé publique (applicationServerKey) à donner au navigateur pour s'abonner."""
    return b64u(_raw_public(_vapid_key()))


def vapid_header(endpoint: str, now: float | None = None) -> str:
    u = urlparse(endpoint)
    claims = {"aud": f"{u.scheme}://{u.netloc}", "exp": int((now or time.time()) + 12 * 3600), "sub": CONTACT}
    head = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = b64u(json.dumps(claims, separators=(",", ":")).encode())
    key = _vapid_key()
    der = key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    sig = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={head}.{body}.{sig}, k={b64u(_raw_public(key))}"


# ---------------------------------------------------------------- chiffrement aes128gcm (RFC 8291)

def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    h = hmac.HMAC(salt, hashes.SHA256())
    h.update(ikm)
    prk = h.finalize()
    h = hmac.HMAC(prk, hashes.SHA256())
    h.update(info + b"\x01")
    return h.finalize()[:length]


def encrypt(payload: bytes, p256dh: str, auth: str, salt: bytes | None = None,
            server_key: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    ua_pub = unb64u(p256dh)
    secret = unb64u(auth)
    as_key = server_key or ec.generate_private_key(ec.SECP256R1())
    as_pub = _raw_public(as_key)
    shared = as_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = _hkdf(secret, shared, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    body = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)          # \x02 : dernier (et seul) bloc
    rs = 4096
    return salt + rs.to_bytes(4, "big") + bytes([len(as_pub)]) + as_pub + body


# ---------------------------------------------------------------- abonnements

def subscriptions() -> list[dict]:
    with db.conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM push_subscriptions ORDER BY id").fetchall()]


def subscribe(sub: dict, device: str = "", fallback: str = "") -> dict:
    """device : nom donné par l'appli ; fallback : navigateur (seulement pour un nouvel abonnement sans nom)."""
    endpoint = str(sub.get("endpoint") or "")
    keys = sub.get("keys") or {}
    u = urlparse(endpoint)
    if u.scheme != "https" or not u.netloc or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("abonnement invalide")
    if len(unb64u(keys["p256dh"])) != 65 or len(unb64u(keys["auth"])) != 16:
        raise ValueError("clés d'abonnement invalides")
    with db.conn() as c:
        c.execute("INSERT INTO push_subscriptions (endpoint, p256dh, auth, device, created_at) VALUES (?,?,?,?,?) "
                  "ON CONFLICT(endpoint) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth, "
                  "device = CASE WHEN ? != '' THEN ? ELSE push_subscriptions.device END, failures = 0",
                  (endpoint, keys["p256dh"], keys["auth"], (device or fallback)[:120], time.time(), device[:120], device[:120]))
    return {"ok": True, "devices": len(subscriptions())}


def unsubscribe(endpoint: str) -> bool:
    with db.conn() as c:
        return c.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)).rowcount > 0


def enabled() -> bool:
    return bool(subscriptions())


async def send(title: str, body: str, url: str = "/", tag: str = "",
               buttons: list[list[tuple[str, str]]] | None = None) -> bool:
    """Envoie à tous les appareils abonnés ; abonnements expirés (404 / 410) supprimés. Vrai si un envoi a réussi."""
    subs = subscriptions()
    if not subs:
        return False
    actions = [{"action": d, "title": t} for row in (buttons or []) for t, d in row][:2]   # Android : 2 boutons au plus
    payload = json.dumps({"title": title, "body": body[:1000], "url": url, "tag": tag, "actions": actions},
                         ensure_ascii=False).encode()
    ok = False
    async with httpx.AsyncClient(timeout=15) as client:
        for s in subs:
            try:
                data = encrypt(payload, s["p256dh"], s["auth"])
                if PROVIDER == "mock" and "push.test" not in s["endpoint"]:
                    ok = True
                    continue
                r = await client.post(s["endpoint"], content=data, headers={
                    "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": str(TTL),
                    "Urgency": "high", "Authorization": vapid_header(s["endpoint"]),
                    **({"Topic": "".join(ch for ch in tag if ch.isalnum())[:32]} if tag else {})})
            except (httpx.HTTPError, ValueError) as e:
                log.warning("notification web : %s", e)
                continue
            with db.conn() as c:
                if r.status_code in (404, 410):            # appareil désabonné ou appli désinstallée
                    c.execute("DELETE FROM push_subscriptions WHERE id = ?", (s["id"],))
                    log.info("abonnement web expiré supprimé (%s)", s["device"] or s["id"])
                elif r.status_code < 300:
                    c.execute("UPDATE push_subscriptions SET last_ok = ?, failures = 0 WHERE id = ?", (time.time(), s["id"]))
                    ok = True
                else:
                    c.execute("UPDATE push_subscriptions SET failures = failures + 1 WHERE id = ?", (s["id"],))
                    log.warning("notification web refusée (%s) : %s", r.status_code, r.text[:160])
    return ok
