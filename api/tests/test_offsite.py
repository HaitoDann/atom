"""Copies chiffrées sur le NAS : chiffrement, envoi, élagage, test de restauration, alertes (NAS simulé par un dossier)."""

import asyncio

import pytest

PHRASE = "phrase de test assez longue"


@pytest.fixture
def nas(client, tmp_path, monkeypatch):
    d = tmp_path / "nas"
    d.mkdir()
    monkeypatch.setenv("ATOM_OFFSITE_DIR", str(d))
    monkeypatch.setenv("ATOM_OFFSITE_KEY", PHRASE)
    monkeypatch.setenv("ATOM_OFFSITE_NAME", "NAS-VinX")
    monkeypatch.setenv("ATOM_OFFSITE_KEEP", "3")
    from app import db
    db.kv_set("offsite:state", "{}")
    return d


def test_encrypt_roundtrip_and_tamper():
    from app.offsite import decrypt, encrypt

    blob = encrypt(b"SQLite format 3 contenu", PHRASE)
    assert blob.startswith(b"ATOMBK1") and b"contenu" not in blob
    assert decrypt(blob, PHRASE) == b"SQLite format 3 contenu"
    with pytest.raises(ValueError, match="phrase incorrecte"):
        decrypt(blob, "mauvaise phrase")
    bad = bytearray(blob)
    bad[-1] ^= 1
    with pytest.raises(ValueError, match="altérée"):
        decrypt(bytes(bad), PHRASE)
    with pytest.raises(ValueError, match="pas une copie"):
        decrypt(b"n'importe quoi", PHRASE)


def test_push_verify_prune_restore(nas):
    from app import backup, db, offsite

    db.add_memory("Le NAS s'appelle NAS-VinX", "test", None)
    names = []
    for i in range(4):
        info = backup.create(f"t{chr(97 + i)}")
        names.append(offsite.push(backup.path_of(info["name"]))["name"])
    remote = [c["name"] for c in offsite.list_remote()]
    assert len(remote) == 3 and names[0] not in remote          # élagage : 3 gardées
    assert not list(nas.glob("*.part"))                          # écriture atomique
    raw = (nas / remote[0]).read_bytes()
    assert b"NAS-VinX" not in raw                                # chiffré sur le NAS
    res = offsite.verify()
    assert res["ok"] and res["counts"]["memories"] >= 1
    st = offsite.status()
    assert st["reachable"] and st["count"] == 3 and st["last_verify_ok"] and st["target"] == "NAS-VinX"
    out = offsite.restore(remote[0])
    assert out["previous"].endswith("-prerestore.db")


def test_unreachable_nas_alerts(client, tmp_path, monkeypatch):
    from app import backup, notify, offsite

    monkeypatch.setenv("ATOM_OFFSITE_DIR", str(tmp_path / "absent"))
    monkeypatch.setenv("ATOM_OFFSITE_KEY", PHRASE)
    from app import db
    db.kv_set("offsite:state", "{}")
    sent = []

    async def fake_send(title, body, conversation_id=None, tags=""):
        sent.append((title, body))
        return True
    monkeypatch.setattr(notify, "send", fake_send)
    info = backup.create("manual")
    asyncio.run(offsite.after_backup(backup.path_of(info["name"])))
    asyncio.run(offsite.after_backup(backup.path_of(info["name"])))   # 2e échec : pas de 2e alerte (anti-spam)
    assert len(sent) == 1 and "échec" in sent[0][0] and "monté" in sent[0][1]
    assert "envoi" in offsite.status()["last_error"]


def test_failed_verification_alerts(nas, monkeypatch):
    from app import backup, notify, offsite

    info = backup.create("manual")
    offsite.push(backup.path_of(info["name"]))
    monkeypatch.setenv("ATOM_OFFSITE_KEY", "phrase changée par erreur")
    sent = []

    async def fake_send(title, body, conversation_id=None, tags=""):
        sent.append(title)
        return True
    monkeypatch.setattr(notify, "send", fake_send)
    assert asyncio.run(offsite.verify_and_alert()) is None
    assert sent and offsite.status()["last_verify_ok"] is False


def test_routes_and_health(client, nas):
    st = client.get("/api/offsite").json()
    assert st["configured"] and st["count"] == 0
    r = client.post("/api/offsite/push")
    assert r.status_code == 200 and r.json()["status"]["count"] == 1
    assert client.post("/api/offsite/verify").json()["ok"] is True
    checks = client.get("/api/status").json()["checks"]
    nas_check = next(c for c in checks if c["name"] == "Copie sur NAS-VinX")
    assert nas_check["status"] == "ok" and "chiffrée" in nas_check["detail"]


def test_not_configured(client, monkeypatch):
    monkeypatch.delenv("ATOM_OFFSITE_DIR", raising=False)
    assert client.post("/api/offsite/push").status_code == 400
    checks = client.get("/api/status").json()["checks"]
    assert next(c for c in checks if c["name"].startswith("Copie sur"))["status"] == "off"
