"""Sauvegardes de la base d'Atom (conversations, mémoire, rappels, lien).

- Une copie automatique chaque nuit, les N dernières sont gardées.
- Export / import d'un fichier depuis l'interface.
- Avant toute restauration, l'état actuel est sauvegardé (rien n'est perdu par erreur).
La copie utilise l'API de sauvegarde de SQLite : cohérente même si Atom écrit au même moment.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from .config import BACKUP_DIR, BACKUP_KEEP, BACKUP_TIME, DB_PATH
from .reminders import TZ

log = logging.getLogger("atom.backup")
NAME_RE = re.compile(r"^atom-\d{8}-\d{6}(-[a-z]+)?\.db$")
REQUIRED = {"conversations", "messages", "memories"}


def _dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def snapshot(dest: Path) -> Path:
    """Copie cohérente de la base vers dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    src = sqlite3.connect(DB_PATH)
    try:
        out = sqlite3.connect(tmp)
        with out:
            src.backup(out)
        out.close()
    finally:
        src.close()
    os.replace(tmp, dest)
    return dest


def create(tag: str = "") -> dict:
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    path = _dir() / f"atom-{stamp}{'-' + tag if tag else ''}.db"
    snapshot(path)
    prune()
    log.info("sauvegarde créée : %s", path.name)
    return describe(path)


def describe(p: Path) -> dict:
    st = p.stat()
    return {"name": p.name, "size": st.st_size, "created_at": st.st_mtime, "tag": p.stem.split("-")[3] if p.stem.count("-") >= 3 else ""}


def list_all() -> list[dict]:
    return sorted((describe(p) for p in _dir().glob("atom-*.db") if NAME_RE.match(p.name)),
                  key=lambda d: d["created_at"], reverse=True)


def prune() -> None:
    """Garde les BACKUP_KEEP dernières sauvegardes automatiques (les autres types sont gardés 5 par type)."""
    groups: dict[str, list[dict]] = {}
    for b in list_all():
        groups.setdefault(b["tag"], []).append(b)
    for tag, items in groups.items():
        keep = BACKUP_KEEP if tag in ("", "auto") else 5
        for b in items[keep:]:
            try:
                (_dir() / b["name"]).unlink()
            except OSError:
                pass


def validate(path: Path) -> None:
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("fichier endommagé")
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            c.close()
    except sqlite3.DatabaseError as e:
        raise ValueError("ce n'est pas une sauvegarde Atom valide") from e
    if not REQUIRED <= tables:
        raise ValueError("ce fichier n'est pas une sauvegarde Atom (tables manquantes)")


def restore_file(src: Path) -> dict:
    """Remplace la base par src, après avoir sauvegardé l'état actuel."""
    validate(src)
    before = create("prerestore")
    tmp = DB_PATH.with_suffix(".restore")
    tmp.write_bytes(src.read_bytes())
    os.replace(tmp, DB_PATH)
    from . import db
    db.init()   # met à niveau le schéma si la sauvegarde est ancienne
    log.info("base restaurée depuis %s (état précédent : %s)", src.name, before["name"])
    return {"restored": src.name, "previous": before["name"]}


def path_of(name: str) -> Path:
    if not NAME_RE.match(name):
        raise ValueError("nom de sauvegarde invalide")
    p = _dir() / name
    if not p.exists():
        raise FileNotFoundError(name)
    return p


def _next_run(now: datetime) -> datetime:
    h, m = (int(x) for x in BACKUP_TIME.split(":"))
    nxt = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return nxt if nxt > now else nxt + timedelta(days=1)


async def scheduler() -> None:
    log.info("sauvegarde quotidienne à %s (%d gardées) dans %s", BACKUP_TIME, BACKUP_KEEP, BACKUP_DIR)
    # Rattrapage : si aucune sauvegarde depuis 24 h (serveur éteint la nuit), on en fait une.
    try:
        last = list_all()
        if DB_PATH.exists() and (not last or time.time() - last[0]["created_at"] > 86400):
            await asyncio.to_thread(create, "auto")
    except Exception:
        log.exception("sauvegarde de rattrapage impossible")
    while True:
        now = datetime.now(TZ)
        await asyncio.sleep(max(30, (_next_run(now) - now).total_seconds()))
        try:
            info = await asyncio.to_thread(create, "auto")
        except Exception:
            log.exception("sauvegarde quotidienne impossible")
            continue
        from . import offsite
        await offsite.after_backup(_dir() / info["name"])   # copie chiffrée sur le NAS (si configurée)
