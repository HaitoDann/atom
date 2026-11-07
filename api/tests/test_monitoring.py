"""Alertes de consommation, relais Grafana et cohérence du tableau de bord avec /api/metrics."""

import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest

from conftest import chat

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- alertes


@pytest.fixture
def fresh_alerts(client, monkeypatch):
    from app import db, notify
    with db.conn() as c:            # journal vide : les appels des autres tests ne faussent pas les seuils
        c.execute("DELETE FROM api_usage")
    db.kv_set("alerts:sent", "{}")
    db.kv_set("alerts:log", "[]")
    sent = []

    async def fake_send(title, body, conversation_id=None, tags=""):
        sent.append((title, body, tags))
        return True
    monkeypatch.setattr(notify, "send", fake_send)
    return sent


def test_quota_alert_once_per_day(fresh_alerts, monkeypatch):
    from app import alerts, providers

    p = providers.Provider("qx", "Groq", "u", "k", "m", 100, "llama", 2, True)
    monkeypatch.setattr(providers, "ALL", [p])
    monkeypatch.setattr(providers, "used_today", lambda pid: 85)
    asyncio.run(alerts.check())
    asyncio.run(alerts.check())
    assert len(fresh_alerts) == 1 and "Quota Groq à 85 %" in fresh_alerts[0][0]
    assert alerts.history()[0]["kind"] == "quota"


def test_down_alert(fresh_alerts, monkeypatch):
    from app import alerts, providers, usage

    monkeypatch.setattr(providers, "ALL", [])
    for _ in range(3):
        usage.record("groq", ok=False, error="503", task="simple")
    asyncio.run(alerts.check())
    assert any("en panne" in t for t, _, _ in fresh_alerts)
    n = len(fresh_alerts)
    asyncio.run(alerts.check())                 # pas de répétition avant 2 h
    assert len(fresh_alerts) == n


def test_no_down_alert_when_one_succeeds(fresh_alerts, monkeypatch):
    from app import alerts, providers, usage

    monkeypatch.setattr(providers, "ALL", [])
    for ok in (False, False, False, True):
        usage.record("groq2", ok=ok, task="simple")
    assert not [a for a in alerts.pending() if a[1] == "down"]


def test_budget_alert(fresh_alerts, monkeypatch):
    from app import alerts, providers, usage

    monkeypatch.setattr(providers, "ALL", [])
    monkeypatch.setenv("ATOM_COST_BUDGET", "1")
    monkeypatch.setenv("ATOM_PRICEY_PRICE_OUT", "1000000")      # 1 $ par token : budget vite atteint
    usage.record("pricey", ok=True, completion_tokens=1)
    asyncio.run(alerts.check())
    assert any("Budget API dépassé" in t for t, _, _ in fresh_alerts)
    assert alerts.status()["month_cost"] >= 1


def test_alert_routes(client, fresh_alerts):
    assert client.post("/api/alerts/test").status_code == 200
    assert fresh_alerts and "Test" in fresh_alerts[-1][0]
    snap = client.get("/api/usage").json()
    assert "alerts" in snap and snap["grafana"] is False


# ---------------------------------------------------------------- relais Grafana


@pytest.fixture
def grafana_up(client, monkeypatch):
    from app import grafana

    monkeypatch.setenv("ATOM_GRAFANA_URL", "http://grafana:3000")
    seen = {}

    def handler(req):
        seen.update(url=str(req.url), cookie=req.headers.get("cookie", ""), method=req.method, body=req.content,
                    host=req.headers.get("host"))
        # flux non lu, comme une vraie réponse réseau
        return httpx.Response(200, stream=httpx.ByteStream(b"<html>grafana</html>"),
                              headers={"content-type": "text/html", "content-security-policy": "script-src 'self' 'unsafe-eval'"})
    monkeypatch.setattr(grafana, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return seen


def test_grafana_proxy(client, grafana_up):
    client.cookies.set("grafana_session", "g1")
    r = client.get("/grafana/d/atom/atom?kiosk")
    assert r.status_code == 200 and "grafana" in r.text
    assert grafana_up["url"] == "http://grafana:3000/grafana/d/atom/atom?kiosk"
    assert "grafana_session=g1" in grafana_up["cookie"] and "atom" not in grafana_up["cookie"].replace("grafana", "")
    assert r.headers["x-frame-options"] == "SAMEORIGIN"                       # affichable dans l'interface
    assert "unsafe-eval" in r.headers["content-security-policy"]              # la CSP de Grafana, pas celle d'Atom
    r = client.post("/grafana/api/ds/query", json={"q": 1}, headers={"Origin": "http://testserver"})   # requêtes des panneaux
    assert r.status_code == 200 and grafana_up["method"] == "POST" and b'"q"' in grafana_up["body"]
    assert grafana_up["host"] == "testserver"     # Host = adresse vue par le navigateur, sinon Grafana refuse l'Origin


def test_grafana_requires_session(grafana_up):
    from fastapi.testclient import TestClient

    from app import main
    assert TestClient(main.app).get("/grafana/d/atom/atom").status_code == 401


def test_grafana_disabled_or_down(client, monkeypatch):
    from app import grafana

    monkeypatch.delenv("ATOM_GRAFANA_URL", raising=False)
    assert client.get("/grafana/").status_code == 404
    monkeypatch.setenv("ATOM_GRAFANA_URL", "http://grafana:3000")

    def down(req):
        raise httpx.ConnectError("refusé", request=req)
    monkeypatch.setattr(grafana, "_client", httpx.AsyncClient(transport=httpx.MockTransport(down)))
    r = client.get("/grafana/")
    assert r.status_code == 502 and "injoignable" in r.json()["detail"]


# ---------------------------------------------------------------- tableau de bord


def _dashboard() -> dict:
    return json.loads((ROOT / "monitoring/grafana/dashboards/atom.json").read_text())


def test_dashboard_metrics_exist(client):
    chat(client, "Bonjour")
    exposed = set(re.findall(r"^# TYPE (\w+)", client.get("/api/metrics").text, re.M))
    dash = _dashboard()
    used = set()
    for p in dash["panels"]:
        for t in p.get("targets", []):
            used |= set(re.findall(r"\b(atom_\w+)", t["expr"]))
            assert t["datasource"]["uid"] == "atom-prometheus"
            assert t["expr"].count("(") == t["expr"].count(")"), t["expr"]
    base = {re.sub(r"_(bucket|sum|count)$", "", m) for m in used}
    assert base <= exposed, f"métriques absentes de /api/metrics : {base - exposed}"


def test_dashboard_layout_and_provisioning():
    dash = _dashboard()
    ids = [p["id"] for p in dash["panels"]]
    assert len(ids) == len(set(ids)) and dash["uid"] == "atom"
    cells = set()
    for p in dash["panels"]:
        g = p["gridPos"]
        assert g["x"] + g["w"] <= 24
        for x in range(g["x"], g["x"] + g["w"]):
            for y in range(g["y"], g["y"] + g["h"]):
                assert (x, y) not in cells, f"panneaux superposés : {p['title']}"
                cells.add((x, y))
    ds = (ROOT / "monitoring/grafana/provisioning/datasources/prometheus.yml").read_text()
    assert "uid: atom-prometheus" in ds and "http://prometheus:9090" in ds
    prom = (ROOT / "monitoring/prometheus.yml").read_text()
    assert "/api/metrics" in prom and "__ATOM_METRICS_TOKEN__" in prom


def test_dashboard_promql_syntax():
    """Chaque requête du tableau (et des annotations) est du PromQL valide."""
    promql_parser = pytest.importorskip("promql_parser")
    dash = _dashboard()
    exprs = [(p["title"], t["expr"]) for p in dash["panels"] for t in p.get("targets", [])]
    exprs += [(a["name"], a["expr"]) for a in dash["annotations"]["list"] if "expr" in a]
    errors = []
    for title, e in exprs:
        try:
            promql_parser.parse(e.replace("$__range", "1h").replace("$__rate_interval", "1m"))
        except Exception as ex:  # noqa: BLE001 — on collecte toutes les erreurs pour le rapport
            errors.append(f"{title} : {ex}")
    assert not errors, errors
    assert len(exprs) > 40


def test_grafana_check_reports_exact_errors(client, monkeypatch):
    from app import grafana

    monkeypatch.setenv("ATOM_GRAFANA_URL", "http://grafana:3000")
    dash = {"dashboard": {"panels": [
        {"title": "Bon", "targets": [{"refId": "A", "datasource": {"uid": "atom-prometheus"}, "expr": "up"}]},
        {"title": "Cassé", "targets": [{"refId": "A", "datasource": {"uid": "atom-prometheus"}, "expr": "foo("}]},
        {"title": "Vide", "targets": [{"refId": "A", "datasource": {"uid": "atom-prometheus"}, "expr": "absent_metric"}]},
        {"title": "Rangée", "type": "row"}]}}

    def handler(req):
        if req.url.path.endswith("/api/dashboards/uid/atom"):
            return httpx.Response(200, json=dash)
        q = json.loads(req.content)["queries"][0]["expr"]
        if q == "foo(":
            return httpx.Response(400, json={"results": {"A": {"error": "bad_data: parse error: unclosed left parenthesis"}}})
        values = [[1, 2], [3, 4]] if q == "up" else []
        return httpx.Response(200, json={"results": {"A": {"frames": [{"data": {"values": values}}]}}})
    monkeypatch.setattr(grafana, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    r = client.get("/api/monitoring/check").json()
    assert r["checked"] == 3 and not r["ok"]
    assert r["errors"] == [{"panel": "Cassé", "error": "bad_data: parse error: unclosed left parenthesis", "query": "A"}]
    assert r["empty"] == ["Vide"]
