"""Génère monitoring/grafana/dashboards/atom.json (tableau de bord Grafana d'Atom).

Usage : python monitoring/build_dashboard.py
Le JSON produit est versionné ; ce script sert à le modifier sans éditer 1 000 lignes à la main.
Les requêtes utilisent les métriques de /api/metrics (api/app/observability.py).
"""

import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "atom-prometheus"}
GREY = ["#e6e6e6", "#b5b5b5", "#8a8a8a", "#6a6a6a", "#4a4a4a"]
_id = 0


def nid() -> int:
    global _id
    _id += 1
    return _id


def target(expr: str, legend: str = "", ref: str = "A", instant: bool = False) -> dict:
    t = {"datasource": DS, "expr": expr, "legendFormat": legend or "__auto", "refId": ref, "range": not instant}
    if instant:
        t["instant"] = True
    return t


def stat(title: str, expr: str, x: int, y: int, unit: str = "short", desc: str = "", decimals: int | None = None,
         thresholds: list | None = None, w: int = 4) -> dict:
    p = {"id": nid(), "type": "stat", "title": title, "description": desc, "datasource": DS,
         "gridPos": {"h": 4, "w": w, "x": x, "y": y}, "targets": [target(expr, instant=True)],
         "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "value",
                     "graphMode": "none", "justifyMode": "auto", "textMode": "value", "orientation": "auto"},
         "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "thresholds"},
                                      "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": GREY[0], "value": None}]}},
                         "overrides": []}}
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    return p


def series(title: str, targets: list[dict], x: int, y: int, w: int = 12, h: int = 8, unit: str = "short",
           stack: bool = False, desc: str = "", kind: str = "line") -> dict:
    return {"id": nid(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": h, "w": w, "x": x, "y": y}, "targets": targets,
            "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}},
            "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "palette-classic"},
                                         "custom": {"drawStyle": "bars" if kind == "bars" else "line", "lineWidth": 2,
                                                    "fillOpacity": 70 if kind == "bars" else 12, "showPoints": "never",
                                                    "stacking": {"mode": "normal" if stack else "none", "group": "A"},
                                                    "spanNulls": True}},
                            "overrides": []}}


def bars(title: str, expr: str, legend: str, x: int, y: int, w: int = 8, h: int = 7, unit: str = "percentunit",
         steps: list | None = None, desc: str = "", mx: float | None = 1) -> dict:
    d = {"unit": unit, "min": 0, "color": {"mode": "thresholds"},
         "thresholds": {"mode": "absolute", "steps": steps or [{"color": "#e05d5d", "value": None}, {"color": "#e8c76a", "value": 0.2},
                                                                {"color": "#8fd19e", "value": 0.5}]}}
    if mx is not None:
        d["max"] = mx
    return {"id": nid(), "type": "bargauge", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": h, "w": w, "x": x, "y": y}, "targets": [target(expr, legend, instant=True)],
            "options": {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True, "valueMode": "color",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "minVizHeight": 16},
            "fieldConfig": {"defaults": d, "overrides": []}}


def row(title: str, y: int) -> dict:
    return {"id": nid(), "type": "row", "title": title, "collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}


ERR = [{"color": "#8fd19e", "value": None}, {"color": "#e8c76a", "value": 0.05}, {"color": "#e05d5d", "value": 0.2}]

panels = [
    row("Vue d'ensemble", 0),
    stat("Appels aux modèles", 'sum(increase(atom_model_calls_total[$__range]))', 0, 1, decimals=0,
         desc="Appels au modèle local et aux API sur la période affichée."),
    stat("Tokens", 'sum(increase(atom_model_tokens_total[$__range]))', 4, 1, decimals=0),
    stat("Taux d'échec", 'sum(increase(atom_model_calls_total{result="error"}[$__range])) / clamp_min(sum(increase(atom_model_calls_total[$__range])), 1)',
         8, 1, unit="percentunit", decimals=1, thresholds=ERR),
    stat("Bascules", 'sum(increase(atom_model_fallback_total[$__range]))', 12, 1, decimals=0,
         desc="Réponses obtenues après l'échec d'un premier fournisseur (relais automatique)."),
    stat("Coût estimé", 'sum(increase(atom_model_cost_dollars_total[$__range]))', 16, 1, unit="currencyUSD", decimals=2,
         desc="Selon les tarifs ATOM_<ID>_PRICE_IN / _PRICE_OUT."),
    stat("Temps de réponse HTTP (p95)", 'histogram_quantile(0.95, sum by (le) (rate(atom_http_request_duration_seconds_bucket[5m])))',
         20, 1, unit="s", decimals=2, thresholds=[{"color": "#8fd19e", "value": None}, {"color": "#e8c76a", "value": 1}, {"color": "#e05d5d", "value": 5}]),

    row("Modèles et fournisseurs d'IA", 5),
    series("Tokens par minute, par fournisseur",
           [target('sum by (provider) (rate(atom_model_tokens_total[5m])) * 60', "{{provider}}")], 0, 6, stack=True, kind="bars"),
    series("Appels par minute (réussis / en échec)",
           [target('sum by (provider) (rate(atom_model_calls_total{result="ok"}[5m])) * 60', "{{provider}}"),
            target('sum by (provider) (rate(atom_model_calls_total{result="error"}[5m])) * 60', "{{provider}} — échecs", "B")],
           12, 6),
    bars("Quota du jour restant", 'atom_provider_quota_remaining / clamp_min(atom_provider_quota_limit, 1)', "{{provider}}", 0, 14,
         desc="Part du quota quotidien encore disponible. Atom ménage un fournisseur sous 20 %."),
    bars("Réussite (20 derniers appels)", 'atom_provider_success_ratio', "{{provider}}", 8, 14,
         steps=[{"color": "#e05d5d", "value": None}, {"color": "#e8c76a", "value": 0.8}, {"color": "#8fd19e", "value": 0.95}]),
    bars("Délai avant le premier mot", 'atom_provider_latency_seconds', "{{provider}}", 16, 14, unit="s", mx=None,
         steps=[{"color": "#8fd19e", "value": None}, {"color": "#e8c76a", "value": 3}, {"color": "#e05d5d", "value": 8}]),
    series("Temps de génération par minute", [target('sum by (provider) (rate(atom_model_seconds_total[5m])) * 60', "{{provider}}")],
           0, 21, unit="s", desc="Secondes passées à générer par minute : la charge réelle de chaque modèle."),
    series("Bascules et pauses", [target('sum by (provider) (increase(atom_model_fallback_total[15m]))', "bascule vers {{provider}}"),
                                  target('atom_provider_paused', "{{provider}} en pause", "B")], 12, 21),

    row("Serveur web", 29),
    series("Requêtes par seconde, par statut",
           [target('sum by (status) (rate(atom_http_requests_total[5m]))', "{{status}}")], 0, 30, w=8, unit="reqps"),
    series("Durée des requêtes (p50 / p95 / p99)",
           [target('histogram_quantile(0.5, sum by (le) (rate(atom_http_request_duration_seconds_bucket[5m])))', "p50"),
            target('histogram_quantile(0.95, sum by (le) (rate(atom_http_request_duration_seconds_bucket[5m])))', "p95", "B"),
            target('histogram_quantile(0.99, sum by (le) (rate(atom_http_request_duration_seconds_bucket[5m])))', "p99", "C")],
           8, 30, w=8, unit="s"),
    series("Routes les plus lentes (p95)",
           [target('topk(5, histogram_quantile(0.95, sum by (le, route) (rate(atom_http_request_duration_seconds_bucket[5m]))))', "{{route}}")],
           16, 30, w=8, unit="s"),

    row("Base de données et service", 38),
    stat("Taille de la base", 'atom_db_size_bytes', 0, 39, unit="bytes", w=6),
    stat("Messages", 'atom_rows{table="messages"}', 6, 39, decimals=0, w=6),
    stat("Souvenirs", 'atom_rows{table="memories"}', 12, 39, decimals=0, w=6),
    stat("En service depuis", 'atom_uptime_seconds', 18, 39, unit="s", w=6),
]

dashboard = {
    "uid": "atom", "title": "Atom", "description": "Consommation des modèles, fournisseurs d'IA, serveur et base d'Atom.",
    "tags": ["atom"], "timezone": "browser", "schemaVersion": 39, "version": 1, "editable": False,
    "graphTooltip": 1, "refresh": "30s", "time": {"from": "now-24h", "to": "now"},
    "timepicker": {"refresh_intervals": ["15s", "30s", "1m", "5m", "15m"]},
    "templating": {"list": []}, "annotations": {"list": []}, "links": [], "panels": panels,
}

out = Path(__file__).parent / "grafana" / "dashboards" / "atom.json"
out.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n")
print(f"{out} : {sum(1 for p in panels if p['type'] != 'row')} panneaux")
