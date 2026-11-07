"""Cycle de vie des souvenirs."""

from ..db import _columns

NAME = "cycle de vie des souvenirs"


def up(c) -> None:
    """Souvenirs : type (sémantique / procédurale / épisodique), importance, confiance, révision, archivage."""
    cols = _columns(c, "memories")
    for col, ddl in [
        ("kind", "TEXT NOT NULL DEFAULT 'semantique'"),
        ("importance", "INTEGER NOT NULL DEFAULT 2"),      # 1 anecdotique · 2 utile · 3 essentiel
        ("confidence", "REAL NOT NULL DEFAULT 0.8"),
        ("review_at", "REAL"),                             # à revoir après cette date (faits temporaires)
        ("archived_at", "REAL"),                           # remplacé ou périmé : gardé pour l'historique
        ("superseded_by", "INTEGER"),
        ("hits", "INTEGER NOT NULL DEFAULT 0"),
        ("last_used", "REAL"),
    ]:
        if col not in cols:
            c.execute(f"ALTER TABLE memories ADD COLUMN {col} {ddl}")
    c.execute("CREATE INDEX IF NOT EXISTS idx_mem_active ON memories(archived_at, kind)")
