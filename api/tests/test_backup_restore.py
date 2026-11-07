import sqlite3

from app import backup, db


def test_backup_then_restore_roundtrip(client):
    cid = db.create_conversation("Avant sauvegarde")
    db.add_message(cid, "user", "message important")
    b = backup.create("test")
    path = backup.path_of(b["name"])
    # la copie est une base SQLite valide et complète
    with sqlite3.connect(path) as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("SELECT COUNT(*) FROM conversations WHERE id = ?", (cid,)).fetchone()[0] == 1
    # changement après la sauvegarde, puis restauration : on retrouve l'état sauvegardé
    db.delete_conversation(cid)
    assert not db.conversation_exists(cid)
    backup.restore_file(path)
    assert db.conversation_exists(cid)
    assert db.messages(cid, 10)[0]["content"] == "message important"
    assert db.schema_version() >= 2          # migrations toujours en place après restauration
