"""Agenda d'Atom : événements (avec récurrence) et rappels avant chaque rendez-vous."""

NAME = "agenda"


def up(c) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL UNIQUE,                 -- identifiant stable (flux .ics)
            title TEXT NOT NULL,
            start_at REAL NOT NULL,                   -- timestamp UTC du début (1re occurrence)
            end_at REAL NOT NULL,
            all_day INTEGER NOT NULL DEFAULT 0,
            location TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            repeat TEXT NOT NULL DEFAULT '',          -- '' | daily | weekly | monthly | yearly
            repeat_interval INTEGER NOT NULL DEFAULT 1,
            repeat_until REAL,                        -- fin de la récurrence (incluse), NULL = sans fin
            exdates TEXT NOT NULL DEFAULT '[]',       -- débuts d'occurrences supprimées (timestamps)
            remind_min INTEGER,                       -- rappel N minutes avant ; NULL = pas de rappel
            conversation_id INTEGER,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_at)")
