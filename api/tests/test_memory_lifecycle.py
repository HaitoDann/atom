import asyncio
import time

from app import db, memory


def test_contradiction_replaces_and_archives(client):
    db.clear_memories()
    a = asyncio.run(memory.remember("L'utilisateur habite à Lyon.", source="auto"))
    assert a["action"] == "added"
    # même sujet (score « lié » forcé via le mode test) : contradiction détectée → l'ancien est archivé
    orig = memory._top
    memory._top = lambda v, facts, k, s: [(0.8, f) for f in facts][:k]
    try:
        b = asyncio.run(memory.remember("L'utilisateur habite à Nantes.", source="auto"))
    finally:
        memory._top = orig
    assert b["action"] == "replaced" and "Lyon" in b["replaced"]
    active = [m["content"] for m in db.list_memories()]
    assert active == ["L'utilisateur habite à Nantes."]
    old = [m for m in db.list_memories(active_only=False) if m["archived_at"]]
    assert old and old[0]["superseded_by"] == b["id"]


def test_exact_duplicate_raises_confidence(client):
    db.clear_memories()
    asyncio.run(memory.remember("L'utilisateur code en Go.", source="auto"))
    c0 = db.list_memories()[0]["confidence"]
    assert asyncio.run(memory.remember("l'utilisateur code en go.", source="auto")) is None
    assert db.list_memories()[0]["confidence"] > c0


def test_temporary_fact_hidden_after_review_date(client):
    db.clear_memories()
    m = asyncio.run(memory.remember("L'utilisateur est malade cette semaine.", source="auto", temporary=True))
    db.set_memory_fields(m["id"], review_at=time.time() - 10)
    block, used = asyncio.run(memory.context_for("comment je vais ?", 999))
    assert "malade" not in block
    r = client.get("/api/memories").json()["memories"]
    assert r[0]["to_review"] is True
    client.post(f"/api/memories/{m['id']}/meta", json={"confirm": True})
    assert client.get("/api/memories").json()["memories"][0]["to_review"] is False


def test_procedural_section_and_bounded_recall(client):
    db.clear_memories()
    asyncio.run(memory.remember("L'utilisateur préfère des réponses courtes.", source="auto", kind="procedurale", importance=3))
    block, _ = asyncio.run(memory.context_for("explique-moi docker", 999))
    assert "habitudes" in block and "réponses courtes" in block
    assert db.prune_recall(0, 0) >= 0
    assert db.list_recall(5) == [] or len(db.list_recall(5)) <= 5


def test_migrations_recorded(client):
    assert db.schema_version() >= 2
    assert db.migrate() == []          # déjà appliquées : rien à refaire
