"""Copies de sauvegarde hors du serveur (NAS), chiffrées, vérifiées chaque semaine.

- Après chaque sauvegarde automatique, une copie chiffrée part dans ATOM_OFFSITE_DIR (un partage du NAS monté
  par Docker, voir docker-compose.nas.yml). Les ATOM_OFFSITE_KEEP dernières sont gardées.
- Chiffrement AES-256-GCM, clé dérivée de ATOM_OFFSITE_KEY par scrypt : le NAS ne voit jamais tes conversations
  en clair. Sans la phrase, une copie est illisible — garde-la aussi ailleurs que sur le serveur.
- Chaque semaine, la copie la plus récente est déchiffrée et contrôlée (intégrité SQLite, tables, nombre de lignes).
- Tout échec (NAS injoignable, envoi, vérification) te prévient par ntfy / Telegram.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import sqlite3
import tempfile
import time
from hashlib import scrypt
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import db

log = logging.getLogger("atom.offsite")
MAGIC = b"ATOMBK1\n"
NAME_RE = re.compile(r"^atom-\d{8}-\d{6}(-[a-z]+)?\.db\.enc$")
VERIFY_EVERY = 7 * 86400
ALERT_COOLDOWN = 6 * 3600


def _dir() -> Path | None:
    v = os.getenv("ATOM_OFFSITE_DIR", "")
    return Path(v) if v else None


def _key_phrase() -> str:
    return os.getenv("ATOM_OFFSITE_KEY", "")


def keep() -> int:
    try:
        return max(1, int(os.getenv("ATOM_OFFSITE_KEEP", "30")))
    except ValueError:
        return 30


def configured() -> bool:
    return bool(_dir() and _key_phrase())


def target_name() -> str:
    return os.getenv("ATOM_OFFSITE_NAME", "NAS")


# ---------------------------------------------------------------- chiffrement


def _derive(phrase: str, salt: bytes) -> bytes:
    return scrypt(phrase.encode(), salt=salt, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)


def encrypt(data: bytes, phrase: str) -> bytes:
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    return MAGIC + salt + nonce + AESGCM(_derive(phrase, salt)).encrypt(nonce, data, MAGIC)


def decrypt(blob: bytes, phrase: str) -> bytes:
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 28:
        raise ValueError("ce fichier n'est pas une copie chiffrée d'Atom")
    salt, nonce, ct = blob[8:24], blob[24:36], blob[36:]
    try:
        return AESGCM(_derive(phrase, salt)).decrypt(nonce, ct, MAGIC)
    except InvalidTag as e:   # mauvaise phrase ou fichier altéré
        raise ValueError("déchiffrement impossible : phrase incorrecte ou copie altérée") from e


# ---------------------------------------------------------------- état (affiché dans l'interface)


def _state() -> dict:
    try:
        return json.loads(db.kv_get("offsite:state") or "{}")
    except ValueError:
        return {}


def _save(**kw) -> None:
    s = _state()
    s.update(kw)
    db.kv_set("offsite:state", json.dumps(s))


def list_remote() -> list[dict]:
    d = _dir()
    if not d or not d.is_dir():
        return []
    out = []
    for p in d.iterdir():
        if NAME_RE.match(p.name):
            st = p.stat()
            out.append({"name": p.name, "size": st.st_size, "created_at": st.st_mtime})
    return sorted(out, key=lambda x: x["name"], reverse=True)


def status() -> dict:
    s = _state()
    d = _dir()
    reachable = bool(d and d.is_dir() and os.access(d, os.W_OK))
    copies = list_remote() if reachable else []
    return {"configured": configured(), "target": target_name(), "dir": str(d) if d else "", "reachable": reachable,
            "keep": keep(), "copies": copies[:10], "count": len(copies), **s}


# ---------------------------------------------------------------- envoi, vérification, restauration


def push(backup_path: Path) -> dict:
    """Chiffre une sauvegarde locale et l'écrit sur le NAS (écriture atomique), puis élague les anciennes copies."""
    if not configured():
        raise RuntimeError("copie distante non configurée (ATOM_OFFSITE_DIR et ATOM_OFFSITE_KEY)")
    d = _dir()
    if not d.is_dir():
        raise RuntimeError(f"{target_name()} injoignable : {d} n'est pas monté")
    t0 = time.time()
    blob = encrypt(backup_path.read_bytes(), _key_phrase())
    dest = d / (backup_path.name + ".enc")
    tmp = d / (dest.name + ".part")
    tmp.write_bytes(blob)
    os.replace(tmp, dest)
    if dest.stat().st_size != len(blob):
        raise RuntimeError("copie incomplète sur le NAS")
    _prune(d)
    info = {"name": dest.name, "size": len(blob), "seconds": round(time.time() - t0, 2)}
    _save(last_push=time.time(), last_push_name=dest.name, last_error="", last_error_at=None)
    log.info("copie chiffrée envoyée sur %s : %s (%d o)", target_name(), dest.name, len(blob))
    return info


def _prune(d: Path) -> None:
    for c in list_remote()[keep():]:
        try:
            (d / c["name"]).unlink()
        except OSError:
            log.warning("ancienne copie %s non supprimée", c["name"], exc_info=True)


def _decrypt_to(name: str, dest: Path) -> Path:
    d = _dir()
    if not NAME_RE.match(name) or not d:
        raise ValueError("nom de copie invalide")
    src = d / name
    if not src.exists():
        raise FileNotFoundError(name)
    dest.write_bytes(decrypt(src.read_bytes(), _key_phrase()))
    return dest


def verify(name: str | None = None) -> dict:
    """Déchiffre une copie (la plus récente par défaut) dans un fichier temporaire et contrôle qu'elle est restaurable."""
    from . import backup

    copies = list_remote()
    if not copies:
        raise RuntimeError(f"aucune copie sur {target_name()}")
    name = name or copies[0]["name"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _decrypt_to(name, Path(tmp) / "verif.db")
        backup.validate(path)
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("conversations", "messages", "memories")}
        finally:
            c.close()
    res = {"name": name, "ok": True, "counts": counts, "at": time.time()}
    _save(last_verify=res["at"], last_verify_name=name, last_verify_ok=True, last_verify_counts=counts, last_verify_error="")
    log.info("copie %s vérifiée : %s", name, counts)
    return res


def restore(name: str) -> dict:
    """Restaure Atom depuis une copie du NAS (l'état actuel est sauvegardé avant, comme pour une restauration locale)."""
    from . import backup

    with tempfile.TemporaryDirectory() as tmp:
        path = _decrypt_to(name, Path(tmp) / name.removesuffix(".enc"))
        return backup.restore_file(path)


# ---------------------------------------------------------------- alertes et planification


async def _alert(what: str, err: Exception | str) -> None:
    from . import notify

    msg = str(err) or err.__class__.__name__
    _save(last_error=f"{what} : {msg}"[:300], last_error_at=time.time())
    s = _state()
    if time.time() - s.get("last_alert", 0) < ALERT_COOLDOWN:
        return
    _save(last_alert=time.time())
    await notify.send(f"Sauvegarde sur {target_name()} : échec", f"{what} : {msg}\n\nTes données restent sauvegardées "
                      "sur le serveur ; vérifie le NAS (allumé, partage monté).", tags="warning,floppy_disk")


async def after_backup(path: Path) -> None:
    """Appelé après chaque sauvegarde automatique."""
    if not configured():
        return
    try:
        await asyncio.to_thread(push, path)
    except Exception as e:
        log.warning("copie distante impossible", exc_info=True)
        await _alert("envoi de la copie", e)
        return
    if time.time() - _state().get("last_verify", 0) >= VERIFY_EVERY:
        await verify_and_alert()


async def verify_and_alert() -> dict | None:
    try:
        return await asyncio.to_thread(verify)
    except Exception as e:
        log.warning("vérification de la copie distante impossible", exc_info=True)
        _save(last_verify=time.time(), last_verify_ok=False, last_verify_error=str(e)[:300])
        await _alert("test de restauration", e)
        return None
