"""Index des requêtes fréquentes."""

NAME = "index des requêtes fréquentes"


def up(c) -> None:
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_recall_created ON recall(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_recall_conv ON recall(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_rem_status_due ON reminders(status, due_at)",
        "CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at)",
    ):
        c.execute(sql)
    tables = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "chunks" in tables:
        c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_col ON chunks(collection_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id)")
    if "documents" in tables:
        c.execute("CREATE INDEX IF NOT EXISTS idx_docs_col ON documents(collection_id)")
