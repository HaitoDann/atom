"""Notifications Web Push : abonnements des appareils (appli Atom installée sur le téléphone, navigateur)."""

NAME = "notifications web push"


def up(c) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            device TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            last_ok REAL,
            failures INTEGER NOT NULL DEFAULT 0
        )""")
