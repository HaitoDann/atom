"""Migrations versionnées de la base SQLite.

Chaque fichier `mNNN_description.py` définit `NAME` (texte court) et `up(c)` (c : connexion sqlite3).
Le numéro NNN est la version : appliquée une seule fois, dans l'ordre, et enregistrée dans `schema_version`.

Règle : ne jamais modifier une migration publiée, en ajouter une nouvelle (numéro suivant).
"""

from __future__ import annotations

import importlib
import pkgutil
import re


def discover() -> list[tuple[int, str, object]]:
    found = []
    for info in pkgutil.iter_modules(__path__):
        m = re.fullmatch(r"m(\d{3})_\w+", info.name)
        if not m:
            continue
        mod = importlib.import_module(f"{__name__}.{info.name}")
        found.append((int(m.group(1)), mod.NAME, mod.up))
    found.sort(key=lambda x: x[0])
    versions = [v for v, _, _ in found]
    if len(versions) != len(set(versions)):
        raise RuntimeError(f"numéros de migration en double : {versions}")
    return found
