"""Accès protégé par mot de passe.

- Un seul mot de passe (Atom est personnel), stocké haché avec scrypt.
- Au premier lancement, l'interface demande de le créer (ou ATOM_PASSWORD le fixe d'avance).
- Chaque appareil reçoit une session longue (cookie HttpOnly), révocable depuis les réglages.
- Limite d'essais : après 5 échecs en 10 minutes, l'adresse est bloquée de plus en plus longtemps.
- Mot de passe oublié : docker compose exec atom python -m app.auth reset
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sys
import time

from . import db

COOKIE = "atom_session"
SESSION_DAYS = int(os.getenv("ATOM_SESSION_DAYS", "90"))
MIN_LEN = 8
_attempts: dict[str, list[float]] = {}
_blocked: dict[str, float] = {}


def init() -> None:
    with db.conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL UNIQUE,
                device TEXT,
                ip TEXT,
                created_at REAL NOT NULL,
                last_seen REAL NOT NULL,
                expires_at REAL NOT NULL
            )"""
        )
    preset = os.getenv("ATOM_PASSWORD", "")
    if preset and not is_set():
        set_password(preset)


# ---------------------------------------------------------------- mot de passe


def _hash(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32).hex()


def is_set() -> bool:
    return bool(db.kv_get("auth:hash"))


def set_password(password: str) -> None:
    if len(password) < MIN_LEN:
        raise ValueError(f"Le mot de passe doit faire au moins {MIN_LEN} caractères.")
    salt = secrets.token_bytes(16)
    db.kv_set("auth:hash", f"scrypt${salt.hex()}${_hash(password, salt)}")


def check_password(password: str) -> bool:
    stored = db.kv_get("auth:hash") or ""
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(_hash(password, bytes.fromhex(salt)), digest)


# ---------------------------------------------------------------- limite d'essais


def blocked_for(ip: str) -> int:
    until = _blocked.get(ip, 0)
    return max(0, int(until - time.time()))


def record_failure(ip: str) -> None:
    now = time.time()
    hist = [t for t in _attempts.get(ip, []) if now - t < 600] + [now]
    _attempts[ip] = hist
    if len(hist) >= 5:
        # 1 min, puis 5, puis 30 au-delà
        prev = _blocked.get(ip + ":level", 0)
        level = int(prev) + 1
        _blocked[ip + ":level"] = level
        _blocked[ip] = now + (60 if level == 1 else 300 if level == 2 else 1800)
        _attempts[ip] = []


def record_success(ip: str) -> None:
    _attempts.pop(ip, None)
    _blocked.pop(ip, None)
    _blocked.pop(ip + ":level", None)


# ---------------------------------------------------------------- sessions


def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(device: str, ip: str) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    with db.conn() as c:
        c.execute("INSERT INTO sessions (token_hash, device, ip, created_at, last_seen, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                  (_th(token), device[:120], ip, now, now, now + SESSION_DAYS * 86400))
    return token


def session_for(token: str | None) -> dict | None:
    if not token:
        return None
    now = time.time()
    with db.conn() as c:
        r = c.execute("SELECT * FROM sessions WHERE token_hash = ?", (_th(token),)).fetchone()
        if not r:
            return None
        if r["expires_at"] < now:
            c.execute("DELETE FROM sessions WHERE id = ?", (r["id"],))
            return None
        if now - r["last_seen"] > 300:   # session glissante, mise à jour au plus toutes les 5 min
            c.execute("UPDATE sessions SET last_seen = ?, expires_at = ? WHERE id = ?",
                      (now, now + SESSION_DAYS * 86400, r["id"]))
    return dict(r)


def list_sessions() -> list[dict]:
    with db.conn() as c:
        rows = c.execute("SELECT id, device, ip, created_at, last_seen FROM sessions ORDER BY last_seen DESC").fetchall()
    return [dict(r) for r in rows]


def revoke(sid: int | None = None, token: str | None = None, all_but: int | None = None) -> None:
    with db.conn() as c:
        if token:
            c.execute("DELETE FROM sessions WHERE token_hash = ?", (_th(token),))
        elif all_but is not None:
            c.execute("DELETE FROM sessions WHERE id != ?", (all_but,))
        elif sid is not None:
            c.execute("DELETE FROM sessions WHERE id = ?", (sid,))


def reset() -> None:
    """Efface le mot de passe et toutes les sessions (l'interface redemandera d'en créer un)."""
    with db.conn() as c:
        c.execute("DELETE FROM kv WHERE key = 'auth:hash'")
        c.execute("DELETE FROM sessions")


def device_name(ua: str) -> str:
    ua = ua or ""
    os_ = ("iPhone" if "iPhone" in ua else "iPad" if "iPad" in ua else "Android" if "Android" in ua
           else "Windows" if "Windows" in ua else "Mac" if "Mac OS" in ua else "Linux" if "Linux" in ua else "Appareil")
    br = ("Edge" if "Edg/" in ua else "Firefox" if "Firefox" in ua else "Chrome" if "Chrome" in ua
          else "Safari" if "Safari" in ua else "")
    standalone = ""
    return f"{br} · {os_}{standalone}" if br else os_


if __name__ == "__main__":
    if sys.argv[1:] == ["reset"]:
        db.init()
        init()
        reset()
        print("Mot de passe et sessions effacés : ouvre Atom pour en créer un nouveau.")
    else:
        print("Usage : python -m app.auth reset")
