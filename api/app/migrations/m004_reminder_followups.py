"""Relances des rappels : confirmation (« Fait ») et suivi des relances envoyées."""

NAME = "relances des rappels"


def up(c) -> None:
    cols = {r["name"] for r in c.execute("PRAGMA table_info(reminders)")}
    if "acked_at" not in cols:
        c.execute("ALTER TABLE reminders ADD COLUMN acked_at REAL")          # confirmé par l'utilisateur
    if "nudges" not in cols:
        c.execute("ALTER TABLE reminders ADD COLUMN nudges INTEGER NOT NULL DEFAULT 0")   # relances envoyées
    if "last_nudge_at" not in cols:
        c.execute("ALTER TABLE reminders ADD COLUMN last_nudge_at REAL")
    c.execute("CREATE INDEX IF NOT EXISTS idx_rem_unacked ON reminders(status, acked_at)")
