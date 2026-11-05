"""Tests d'Atom : tout tourne en mode test (ATOM_PROVIDER=mock), sans modèle ni Internet."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="atom-tests-"))
os.environ.update({
    "ATOM_PROVIDER": "mock",
    "ATOM_DB": str(_tmp / "atom.db"),
    "ATOM_BACKUP_DIR": str(_tmp / "backups"),
    "ATOM_PROJECTS_DIR": str(_tmp / "projects"),
    "ATOM_SEARXNG_URL": "",
    "ATOM_NTFY_URL": "",
    "ATOM_TELEGRAM_TOKEN": "",
    "ATOM_REMOTE_API_KEY": "test",
    "ATOM_PASSWORD": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASSWORD = "motdepasse-test"


@pytest.fixture(scope="session")
def tmpdir_root():
    return _tmp


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    import app.main as m

    with TestClient(m.app) as c:
        r = c.post("/api/auth/setup", json={"password": PASSWORD})
        assert r.status_code == 200, r.text
        c.headers.update({"X-Atom": "1"})
        yield c


def chat(client, message, **kw):
    """Envoie un message et renvoie la liste des événements NDJSON."""
    import json

    body = {"message": message, "auto_memory": False, "web": "off", "scope": "none", **kw}
    with client.stream("POST", "/api/chat", json=body) as r:
        assert r.status_code == 200, r.read()
        return [json.loads(line) for line in r.iter_lines() if line]
