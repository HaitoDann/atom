"""Génère monitoring/grafana/dashboards/atom.json (tableau de bord Grafana d'Atom).

Usage : python monitoring/build_dashboard.py
Le JSON produit est versionné ; ce script sert à le modifier sans éditer 2 000 lignes à la main.
Les requêtes utilisent les métriques de /api/metrics (api/app/observability.py) ; un test vérifie qu'elles existent.

Principes visuels : une couleur fixe par fournisseur dans tous les panneaux, monochrome pour le reste (comme Atom),
vert / orange / rouge seulement pour les seuils ; « 0 » plutôt que « No data » ; la période se choisit dans Atom.
"""

import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "atom-prometheus"}
INK = "#d8d8d8"
OK, WARN, BAD = "#8fd19e", "#e8c76a", "#e05d5d"
# Une couleur par fournisseur, partout (graphiques, barres, légendes).
PROVIDERS = {"local": "#cfcfcf", "groq": "#f2a65a", "gemini": "#7aa6f0", "openrouter": "#b48cf2", "mistral": "#f28c8c",
             "cerebras": "#6fcf97", "github": "#9aa0a6", "openai": "#5ec8c8", "deepseek": "#7f8cf0"}
TASKS = {"simple": "Question simple", "complexe": "Demande complexe", "code": "Code", "long": "Texte long",
         "agent": "Agent de code", "memoire": "Mémorisation", "embedding": "Embeddings", "autre": "Autre"}
ERRORS = {"quota": "Quota / limite", "cle": "Clé refusée", "trop_long": "Requête trop longue", "modele_absent": "Modèle absent",
          "injoignable": "Injoignable", "reponse_vide": "Réponse vide", "panne": "Panne du fournisseur", "autre": "Autre"}
_id = 0


def nid() -> int:
    global _id
    _id += 1
    return _id


def tgt(expr: str, legend: str = "", ref: str = "A", instant: bool = False) -> dict:
    t = {"datasource": DS, "expr": expr, "legendFormat": legend or "__auto", "refId": ref, "range": not instant}
    if instant:
        t["instant"] = True
    return t


def provider_colors() -> list[dict]:
    """Surcharges de couleur : toute série dont le nom commence par un fournisseur connu prend sa couleur."""
    return [{"matcher": {"id": "byRegexp", "options": f"^{p}\\b.*"},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]} for p, c in PROVIDERS.items()]


def renames(mapping: dict[str, str]) -> list[dict]:
    return [{"matcher": {"id": "byName", "options": k}, "properties": [{"id": "displayName", "value": v}]} for k, v in mapping.items()]


def steps(*pairs) -> dict:
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in pairs]}


def base(kind: str, title: str, x: int, y: int, w: int, h: int, targets: list[dict], desc: str = "") -> dict:
    return {"id": nid(), "type": kind, "title": title, "description": desc, "datasource": DS,
            "gridPos": {"h": h, "w": w, "x": x, "y": y}, "targets": targets, "transparent": False}


def stat(title: str, expr: str, x: int, y: int, w: int = 4, h: int = 4, unit: str = "short", desc: str = "",
         decimals: int | None = 0, thr: dict | None = None, no_value: str = "0", color_mode: str = "value") -> dict:
    p = base("stat", title, x, y, w, h, [tgt(expr, instant=True)], desc)
    p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": color_mode,
                    "graphMode": "none", "justifyMode": "center", "textMode": "value", "orientation": "auto",
                    "text": {"valueSize": 34}}
    d = {"unit": unit, "noValue": no_value, "color": {"mode": "thresholds"}, "thresholds": thr or steps((INK, None))}
    if decimals is not None:
        d["decimals"] = decimals
    p["fieldConfig"] = {"defaults": d, "overrides": []}
    return p


def series(title: str, targets: list[dict], x: int, y: int, w: int = 12, h: int = 8, unit: str = "short", stack: bool = False,
           desc: str = "", bars: bool = False, overrides: list | None = None, fill: int = 10, mn: float | None = 0) -> dict:
    p = base("timeseries", title, x, y, w, h, targets, desc)
    p["options"] = {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                    "tooltip": {"mode": "multi", "sort": "desc"}}
    d = {"unit": unit, "noValue": "0", "color": {"mode": "fixed", "fixedColor": INK},
         "custom": {"drawStyle": "bars" if bars else "line", "lineWidth": 2, "fillOpacity": 80 if bars else fill,
                    "gradientMode": "opacity", "showPoints": "never", "spanNulls": True, "lineInterpolation": "smooth",
                    "barAlignment": 0, "axisBorderShow": False,
                    "stacking": {"mode": "normal" if stack else "none", "group": "A"}}}
    if mn is not None:
        d["min"] = mn
    p["fieldConfig"] = {"defaults": d, "overrides": provider_colors() + (overrides or [])}
    return p


def barg(title: str, expr: str, legend: str, x: int, y: int, w: int = 8, h: int = 8, unit: str = "short",
         thr: dict | None = None, desc: str = "", mx: float | None = None, by_provider: bool = False,
         overrides: list | None = None, decimals: int | None = None) -> dict:
    p = base("bargauge", title, x, y, w, h, [tgt(expr, legend, instant=True)], desc)
    p["options"] = {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True, "valueMode": "color",
                    "namePlacement": "top", "sizing": "auto", "minVizHeight": 14, "maxVizHeight": 26,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}
    d = {"unit": unit, "min": 0, "noValue": "0",
         "color": {"mode": "fixed", "fixedColor": INK} if by_provider and not thr else {"mode": "thresholds"},
         "thresholds": thr or steps((INK, None))}
    if mx is not None:
        d["max"] = mx
    if decimals is not None:
        d["decimals"] = decimals
    p["fieldConfig"] = {"defaults": d, "overrides": (provider_colors() if by_provider and not thr else []) + (overrides or [])}
    return p


def pie(title: str, expr: str, legend: str, x: int, y: int, w: int = 8, h: int = 8, desc: str = "", overrides: list | None = None,
        by_provider: bool = False) -> dict:
    p = base("piechart", title, x, y, w, h, [tgt(expr, legend, instant=True)], desc)
    p["options"] = {"pieType": "donut", "displayLabels": ["percent"], "legend": {"displayMode": "table", "placement": "right",
                    "showLegend": True, "values": ["value"]}, "tooltip": {"mode": "single"},
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}
    p["fieldConfig"] = {"defaults": {"unit": "short", "noValue": "0", "color": {"mode": "palette-classic"}},
                        "overrides": (provider_colors() if by_provider else []) + (overrides or [])}
    return p


def row(title: str, y: int) -> dict:
    return {"id": nid(), "type": "row", "title": title, "collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}


R = "$__range"
CALLS = "atom_model_calls_total"
P50 = 'histogram_quantile(0.5, sum by (le) (rate(atom_model_first_token_seconds_bucket[1h])))'
AGE = steps((OK, None), (WARN, 30 * 3600), (BAD, 48 * 3600))

panels = [
    # ------------------------------------------------------------ santé
    row("Santé", 0),
    stat("Fournisseurs en forme", 'count(atom_provider_success_ratio >= 0.8) or vector(0)', 0, 1,
         desc="Fournisseurs distants avec au moins 80 % de réussite sur leurs 20 derniers appels."),
    stat("Fournisseurs en pause", 'sum(atom_provider_paused) or vector(0)', 4, 1,
         thr=steps((OK, None), (WARN, 1)), desc="Mis en pause quelques minutes après une limite ou une panne."),
    stat("Échecs (1 h)", f'sum(increase({CALLS}{{result="error"}}[1h])) / clamp_min(sum(increase({CALLS}[1h])), 1)', 8, 1,
         unit="percentunit", decimals=1, thr=steps((OK, None), (WARN, 0.05), (BAD, 0.2))),
    stat("Premier mot (médiane, 1 h)", P50, 12, 1, unit="s", decimals=1, no_value="—",
         thr=steps((OK, None), (WARN, 3), (BAD, 8))),
    stat("Dernière sauvegarde", 'time() - atom_backup_last_timestamp_seconds', 16, 1, unit="s", decimals=0,
         no_value="aucune", thr=AGE, desc="Âge de la dernière sauvegarde locale (rouge au-delà de 48 h)."),
    stat("Copie sur le NAS", 'time() - atom_offsite_last_push_timestamp_seconds', 20, 1, unit="s", decimals=0,
         no_value="non configurée", thr=AGE, desc="Âge de la dernière copie chiffrée sur le NAS."),

    # ------------------------------------------------------------ consommation et coût
    row("Consommation et coût", 5),
    stat("Appels", f'sum(increase({CALLS}[{R}]))', 0, 6, w=4, desc="Appels aux modèles (local et API) sur la période."),
    stat("Tokens", f'sum(increase(atom_model_tokens_total[{R}]))', 4, 6, w=4),
    stat("Coût sur la période", f'sum(increase(atom_model_cost_dollars_total[{R}]))', 8, 6, w=4, unit="currencyUSD", decimals=2,
         desc="Selon les tarifs ATOM_<ID>_PRICE_IN / _PRICE_OUT (0 pour les offres gratuites)."),
    {**stat("Budget du mois", 'atom_cost_month_dollars / atom_cost_budget_dollars', 12, 6, w=4, unit="percentunit",
            decimals=0, no_value="pas de budget", thr=steps((OK, None), (WARN, 0.8), (BAD, 1)),
            desc="Part du budget mensuel (ATOM_COST_BUDGET) déjà dépensée."), "type": "gauge",
     "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "showThresholdMarkers": True,
                 "showThresholdLabels": False, "minVizHeight": 60}},
    stat("Bascules", f'sum(increase(atom_model_fallback_total[{R}]))', 16, 6, w=4,
         desc="Réponses obtenues après l'échec d'un premier fournisseur : sans relais, ces réponses auraient échoué."),
    stat("Alertes envoyées", f'sum(increase(atom_alerts_sent_total[{R}])) or vector(0)', 20, 6, w=4,
         thr=steps((INK, None), (WARN, 1))),
    series("Tokens par minute", [tgt('sum by (provider) (rate(atom_model_tokens_total[5m])) * 60', "{{provider}}")],
           0, 10, stack=True, bars=True),
    series("Appels par minute", [tgt(f'sum by (provider) (rate({CALLS}[5m])) * 60', "{{provider}}")], 12, 10, stack=True),

    # ------------------------------------------------------------ routage
    row("Routage : qui répond à quoi", 18),
    pie("Répartition par fournisseur", f'sum by (provider) (increase({CALLS}{{result="ok"}}[{R}]))', "{{provider}}", 0, 19,
        by_provider=True, desc="Réponses réussies sur la période."),
    pie("Répartition par type de demande", f'sum by (task) (increase({CALLS}[{R}]))', "{{task}}", 8, 19,
        overrides=renames(TASKS), desc="Classement fait par Atom avant de choisir le modèle."),
    barg("Type de demande → fournisseur", f'sort_desc(sum by (task, provider) (increase({CALLS}{{result="ok"}}[{R}])) > 0)',
         "{{task}} → {{provider}}", 16, 19, decimals=0, by_provider=True,
         desc="Quel fournisseur a répondu à quel type de demande (le routage intelligent en action)."),
    barg("Erreurs par type", f'sort_desc(sum by (kind) (increase(atom_model_errors_total[{R}])) > 0)', "{{kind}}", 0, 27,
         decimals=0, thr=steps((BAD, None)), overrides=renames(ERRORS),
         desc="Pourquoi les appels ont échoué : quota, clé, panne, modèle absent…"),
    barg("Erreurs par fournisseur", f'sort_desc(sum by (provider) (increase(atom_model_errors_total[{R}])) > 0)', "{{provider}}",
         8, 27, decimals=0, by_provider=True),
    barg("Quota du jour restant", 'atom_provider_quota_remaining / clamp_min(atom_provider_quota_limit, 1)', "{{provider}}",
         16, 27, unit="percentunit", mx=1, thr=steps((BAD, None), (WARN, 0.2), (OK, 0.5)),
         desc="Sous 20 %, Atom ménage le fournisseur ; à 0, il bascule sur les autres."),
    series("Bascules et pauses", [tgt('sum by (provider) (increase(atom_model_fallback_total[10m]))', "{{provider}} (a pris le relais)"),
                                  tgt('atom_provider_paused', "{{provider}} en pause", "B")], 0, 35, w=24, h=7, bars=True),

    # ------------------------------------------------------------ rapidité
    row("Rapidité", 42),
    series("Délai avant le premier mot (médiane)",
           [tgt('histogram_quantile(0.5, sum by (le, provider) (rate(atom_model_first_token_seconds_bucket[15m])))', "{{provider}}")],
           0, 43, w=8, unit="s", desc="Ce que tu ressens : le temps avant que la réponse commence à s'écrire."),
    series("Délai avant le premier mot (cas lents, p95)",
           [tgt('histogram_quantile(0.95, sum by (le, provider) (rate(atom_model_first_token_seconds_bucket[15m])))', "{{provider}}")],
           8, 43, w=8, unit="s"),
    series("Vitesse de génération", [tgt('atom_model_generation_tokens_per_second', "{{provider}}")], 16, 43, w=8,
           unit="short", desc="Tokens écrits par seconde une fois la réponse commencée (dernière heure)."),
    barg("Réussite (20 derniers appels)", 'atom_provider_success_ratio', "{{provider}}", 0, 51, unit="percentunit", mx=1,
         thr=steps((BAD, None), (WARN, 0.8), (OK, 0.95))),
    series("Temps passé à générer, par minute", [tgt('sum by (provider) (rate(atom_model_seconds_total[5m])) * 60', "{{provider}}")],
           8, 51, w=16, unit="s", stack=True, desc="La charge réelle de chaque modèle."),

    # ------------------------------------------------------------ modèle local et serveur
    row("Modèle local et serveur", 59),
    series("Processeur", [tgt('atom_system_cpu_ratio', "processeur")], 0, 60, w=8, unit="percentunit", fill=25,
           overrides=[], mn=0),
    series("Mémoire", [tgt('atom_system_memory_bytes{type="used"}', "utilisée"), tgt('atom_system_memory_bytes{type="total"}', "totale", "B")],
           8, 60, w=8, unit="bytes"),
    stat("Disque libre", 'atom_disk_bytes{type="free"} / atom_disk_bytes{type="total"}', 16, 60, w=4, unit="percentunit",
         decimals=0, thr=steps((BAD, None), (WARN, 0.1), (OK, 0.2)), no_value="—"),
    stat("Modèles chargés (Ollama)", 'atom_ollama_loaded_models', 20, 60, w=4, no_value="—"),
    stat("Mémoire des modèles", 'sum(atom_ollama_loaded_bytes) or vector(0)', 16, 64, w=4, unit="bytes", decimals=1),
    stat("En service depuis", 'atom_uptime_seconds', 20, 64, w=4, unit="s", no_value="—"),

    # ------------------------------------------------------------ qualité
    row("Qualité des réponses", 68),
    stat("Avis positifs", 'atom_feedback_total{value="up"} / clamp_min(sum(atom_feedback_total), 1)', 0, 69, w=6,
         unit="percentunit", decimals=0, no_value="—", thr=steps((BAD, None), (WARN, 0.6), (OK, 0.8)),
         desc="Part des 👍 parmi tes avis sur les réponses (depuis le début)."),
    stat("👍", 'atom_feedback_total{value="up"}', 6, 69, w=3),
    stat("👎", 'atom_feedback_total{value="down"}', 9, 69, w=3),
    series("Avis par jour", [tgt('increase(atom_feedback_total[1d])', "{{value}}")], 12, 69, w=12, h=8, bars=True,
           overrides=renames({"up": "👍", "down": "👎"})),
    stat("Erreurs serveur (5xx, 1 h)", 'sum(increase(atom_http_requests_total{status=~"5.."}[1h])) or vector(0)', 0, 73, w=6,
         thr=steps((OK, None), (WARN, 1), (BAD, 10))),
    stat("Réponses sauvées par un relais", f'sum(increase(atom_model_fallback_total[{R}]))', 6, 73, w=6),

    # ------------------------------------------------------------ mémoire et données
    row("Mémoire et données", 77),
    barg("Souvenirs par type", 'atom_memories', "{{kind}}", 0, 78, w=6, decimals=0,
         overrides=renames({"semantique": "Faits", "procedurale": "Habitudes", "episodique": "Événements"})),
    series("Messages par jour", [tgt('increase(atom_messages_total[1d])', "{{role}}")], 6, 78, w=10, bars=True,
           overrides=renames({"user": "toi", "assistant": "Atom"})),
    stat("Conversations", 'atom_rows{table="conversations"}', 16, 78, w=4),
    stat("Souvenirs", 'atom_rows{table="memories"}', 20, 78, w=4),
    stat("Documents", 'sum(atom_library_documents) or vector(0)', 16, 82, w=4),
    stat("Taille de la base", 'atom_db_size_bytes', 20, 82, w=4, unit="bytes", decimals=1),

    # ------------------------------------------------------------ serveur web
    row("Serveur web", 86),
    series("Requêtes par seconde, par statut", [tgt('sum by (status) (rate(atom_http_requests_total[5m]))', "{{status}}")],
           0, 87, w=8, unit="reqps", stack=True),
    series("Durée des requêtes",
           [tgt('histogram_quantile(0.5, sum by (le) (rate(atom_http_request_duration_seconds_bucket[5m])))', "médiane"),
            tgt('histogram_quantile(0.95, sum by (le) (rate(atom_http_request_duration_seconds_bucket[5m])))', "p95", "B"),
            tgt('histogram_quantile(0.99, sum by (le) (rate(atom_http_request_duration_seconds_bucket[5m])))', "p99", "C")],
           8, 87, w=8, unit="s"),
    series("Routes les plus lentes (p95)",
           [tgt('topk(5, histogram_quantile(0.95, sum by (le, route) (rate(atom_http_request_duration_seconds_bucket[5m]))))', "{{route}}")],
           16, 87, w=8, unit="s"),
]

annotations = {"list": [
    {"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True,
     "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"},
    {"name": "Alertes", "datasource": DS, "enable": True, "iconColor": BAD, "expr": "changes(atom_alerts_sent_total[2m]) > 0",
     "step": "60s", "titleFormat": "Alerte : {{kind}}", "textFormat": "Alerte « {{kind}} » envoyée sur ton téléphone",
     "useValueForTime": False},
    {"name": "Redémarrages", "datasource": DS, "enable": True, "iconColor": "#9aa0a6", "expr": "resets(atom_uptime_seconds[2m]) > 0",
     "step": "60s", "titleFormat": "Atom a redémarré", "textFormat": "Mise à jour ou redémarrage", "useValueForTime": False},
]}

dashboard = {
    "uid": "atom", "title": "Atom", "description": "Observabilité d'Atom : santé, consommation, routage, rapidité, serveur, qualité, données.",
    "tags": ["atom"], "timezone": "browser", "schemaVersion": 39, "version": 2, "editable": False, "liveNow": False,
    "graphTooltip": 1, "refresh": "30s", "time": {"from": "now-24h", "to": "now"},
    "timepicker": {"hidden": True, "refresh_intervals": ["15s", "30s", "1m", "5m"]},   # la période se choisit dans Atom
    "fiscalYearStartMonth": 0, "weekStart": "monday",
    "templating": {"list": []}, "annotations": annotations, "links": [], "panels": panels,
}

if __name__ == "__main__":
    out = Path(__file__).parent / "grafana" / "dashboards" / "atom.json"
    out.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n")
    print(f"{out} : {sum(1 for p in panels if p['type'] != 'row')} panneaux, {sum(1 for p in panels if p['type'] == 'row')} rangées")
