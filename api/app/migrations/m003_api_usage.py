"""Journal des appels aux modèles (local et API) : consommation, latence, bascules, choix du routage."""

NAME = "journal des appels aux modèles"


def up(c) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            provider TEXT NOT NULL,          -- id du fournisseur, « local » pour Ollama
            model TEXT,
            task TEXT,                       -- simple | complexe | code | long | agent…
            ok INTEGER NOT NULL,
            first_s REAL,                    -- délai avant le premier mot
            total_s REAL,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            error TEXT,
            reason TEXT,                     -- pourquoi ce fournisseur (routage) ou bascule
            fallback_from TEXT               -- fournisseur abandonné juste avant (bascule automatique)
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_usage_ts ON api_usage(ts)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_usage_prov_ts ON api_usage(provider, ts)")
