"use strict";

/* ============================================================
   CONSOMMATION — appels aux modèles en direct, quotas, routage
   ============================================================ */
// Ouvert seulement quand la rubrique est affichée : un flux NDJSON (/api/usage/live) pousse chaque appel terminé.
const TASK_LABELS = { simple: "Question simple", complexe: "Demande complexe", code: "Code", long: "Texte long", agent: "Agent de code",
  memoire: "Mémorisation", embedding: "Embeddings" };   // les deux derniers : travail en coulisse du modèle local
let usDays = 1, usState = null, usCtrl = null, usTimer = 0;

const fmtN = (n) => (n || 0).toLocaleString("fr-FR");
const fmtTok = (n) => !n ? "0" : n >= 1e6 ? (n / 1e6).toFixed(1).replace(".", ",") + " M" : n >= 1e4 ? Math.round(n / 1e3) + " k" : fmtN(n);
const fmtCost = (c) => !c ? "—" : c < 0.01 ? "< 0,01 $" : c.toFixed(2).replace(".", ",") + " $";
const fmtS = (s) => s == null ? "—" : s < 1 ? Math.round(s * 1000) + " ms" : s.toFixed(1).replace(".", ",") + " s";
const provName = (id) => id === "local" ? "Local (Ollama)" : (usState?.providers.find((p) => p.id === id)?.name || id);

function usageOpen() {
  usageClose();
  usCtrl = new AbortController();
  $("usLive").classList.remove("on");
  if (usDays !== 1) { loadUsage(); return; }   // le direct ne concerne que la journée
  usageStream(usCtrl.signal).catch(() => {}).finally(() => {
    $("usLive").classList.remove("on");
    // flux coupé (réseau, redémarrage) : on retente tant que la rubrique est ouverte
    if (usCtrl && !usCtrl.signal.aborted && usageVisible()) usTimer = setTimeout(usageOpen, 5000);
  });
}
function usageClose() { clearTimeout(usTimer); usCtrl?.abort(); usCtrl = null; }
const usageVisible = () => $("settings").classList.contains("open") && document.querySelector('.pane[data-pane="usage"]').classList.contains("on");

async function usageStream(signal) {
  const r = await fetch("/api/usage/live", { signal, headers: { "X-Atom": "1" } });
  if (!r.ok) throw new Error(String(r.status));
  const reader = r.body.getReader(), dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1);
      if (!line) continue;
      const ev = JSON.parse(line);
      $("usLive").classList.add("on");
      if (ev.type === "snapshot") { usState = ev; renderUsage(); }
      else if (ev.type === "call" && usState) { usageAdd(ev); }
      if (!usageVisible()) { usageClose(); return; }
    }
  }
}
async function loadUsage() { usState = await getJSON(`/api/usage?days=${usDays}`); renderUsage(); }

/* Un appel arrive : on met à jour les compteurs sans attendre le prochain état complet. */
function usageAdd(ev) {
  usState.recent = [ev, ...usState.recent].slice(0, 40);
  let s = usState.summary.find((x) => x.provider === ev.provider);
  if (!s) { s = { provider: ev.provider, calls: 0, ok: 0, errors: 0, prompt_tokens: 0, completion_tokens: 0, rescues: 0, cost: 0 }; usState.summary.push(s); }
  s.calls++; ev.ok ? s.ok++ : s.errors++;
  s.prompt_tokens += ev.prompt_tokens || 0; s.completion_tokens += ev.completion_tokens || 0;
  s.cost = (s.cost || 0) + (ev.cost || 0); if (ev.fallback_from) s.rescues++;
  s.success = Math.round(100 * s.ok / s.calls);
  if (ev.ok && ev.first_s != null) s.first_s = s.first_s == null ? ev.first_s : (s.first_s * (s.ok - 1) + ev.first_s) / s.ok;
  const p = usState.providers.find((x) => x.id === ev.provider);
  if (p) { p.used_today++; p.quota_left = Math.max(0, p.quota_left - 1); }
  const hour = Math.floor(ev.ts / 3600) * 3600;
  let t = usState.timeline.find((x) => x.hour === hour && x.provider === ev.provider);
  if (!t) { t = { hour, provider: ev.provider, calls: 0, tokens: 0, errors: 0 }; usState.timeline.push(t); }
  t.calls++; t.tokens += (ev.prompt_tokens || 0) + (ev.completion_tokens || 0); if (!ev.ok) t.errors++;
  renderUsage(ev.id);
}

function renderUsage(freshId) {
  const st = usState; if (!st) return;
  const sum = st.summary;
  const tot = sum.reduce((a, s) => ({ calls: a.calls + s.calls, tokens: a.tokens + s.prompt_tokens + s.completion_tokens,
    cost: a.cost + (s.cost || 0), rescues: a.rescues + (s.rescues || 0), errors: a.errors + (s.errors || 0) }), { calls: 0, tokens: 0, cost: 0, rescues: 0, errors: 0 });
  const period = usDays === 1 ? "aujourd'hui" : `sur ${usDays} jours`;
  $("usTiles").innerHTML = [
    ["Appels", fmtN(tot.calls), tot.errors ? `${fmtN(tot.errors)} en échec` : period],
    ["Tokens", fmtTok(tot.tokens), period],
    ["Bascules", fmtN(tot.rescues), "réponses sauvées par un relais"],
    ["Coût estimé", fmtCost(tot.cost), "selon tes tarifs"],
  ].map(([k, v, s]) => `<div class="us-tile"><small>${k}</small><b>${v}</b><span>${esc(s)}</span></div>`).join("");
  renderUsageChart(st.timeline);

  // Fournisseurs : ceux configurés, plus le local, plus ceux vus dans le journal.
  const ids = ["local", ...st.providers.map((p) => p.id), ...sum.map((s) => s.provider)].filter((v, i, a) => a.indexOf(v) === i);
  $("usProv").innerHTML = ids.map((id) => {
    const s = sum.find((x) => x.provider === id) || {}, p = st.providers.find((x) => x.id === id);
    const dot = p ? (p.paused ? "error" : !p.configured ? "off" : (p.health?.last_error ? "warn" : "ok")) : (s.errors && !s.ok ? "error" : "ok");
    const quota = p && p.limit ? `<div class="us-q"><div class="bar"><i style="width:${Math.min(100, 100 * p.used_today / p.limit)}%"></i></div><small>${fmtN(p.quota_left)} / ${fmtN(p.limit)}</small></div>` : '<small class="faint">illimité</small>';
    const model = p ? p.model : (st.recent.find((r) => r.provider === id)?.model || "");
    return `<tr><td><div class="us-p"><span class="st-dot ${dot}"></span><div><b>${esc(provName(id))}</b><small>${esc(model)}${p?.paused ? " · en pause" : ""}</small></div></div></td>
      <td>${fmtN(s.calls)}</td><td>${s.success != null ? s.success + " %" : "—"}</td>
      <td>${fmtTok(s.prompt_tokens)} / ${fmtTok(s.completion_tokens)}</td><td>${fmtS(s.first_s ?? p?.health?.latency)}</td><td>${quota}</td><td>${fmtCost(s.cost)}</td></tr>`;
  }).join("");

  renderUsagePrefs();
  $("usFeed").innerHTML = st.recent.length ? st.recent.map((r) => {
    const t = new Date(r.ts * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const tok = r.completion_tokens ? ` · ${fmtTok((r.prompt_tokens || 0) + r.completion_tokens)} tokens` : "";
    const head = `${t} · ${esc(provName(r.provider))}${r.task ? " · " + esc(TASK_LABELS[r.task] || r.task) : ""}${tok}${r.total_s != null ? " · " + fmtS(r.total_s) : ""}`;
    const body = r.ok ? esc(r.reason || r.model || "") : `<span class="us-ko">Échec : ${esc(r.error)}</span>`;
    const fb = r.fallback_from ? `<span class="us-fb">↪ bascule depuis ${esc(provName(r.fallback_from))}</span>` : "";
    return `<li class="${r.id === freshId ? "fresh" : ""}"><small>${head}</small>${fb}${body}</li>`;
  }).join("") : '<li class="none">Aucun appel pour l\'instant : pose une question à Atom.</li>';
}

function renderUsageChart(tl) {
  const now = Math.floor(Date.now() / 3600000) * 3600, hours = [];
  for (let i = 23; i >= 0; i--) hours.push(now - i * 3600);
  const per = hours.map((h) => tl.filter((x) => x.hour === h));
  const max = Math.max(1, ...per.map((xs) => xs.reduce((a, x) => a + x.tokens, 0)));
  $("usChart").innerHTML = `<div class="us-bars">${per.map((xs, i) => {
    const tokens = xs.reduce((a, x) => a + x.tokens, 0), calls = xs.reduce((a, x) => a + x.calls, 0), errs = xs.reduce((a, x) => a + x.errors, 0);
    const label = `${new Date(hours[i] * 1000).getHours()} h : ${fmtN(calls)} appel(s), ${fmtTok(tokens)} tokens${errs ? `, ${errs} échec(s)` : ""}`;
    return `<span title="${esc(label)}"><i style="height:${tokens ? Math.max(4, 100 * tokens / max) : 0}%"${errs ? ' class="ko"' : ""}></i></span>`;
  }).join("")}</div><div class="us-axis"><span>il y a 24 h</span><span>maintenant</span></div>`;
}

function renderUsagePrefs() {
  const st = usState, box = $("usPrefs");
  if (box.contains(document.activeElement)) return;   // ne pas fermer une liste en cours de choix
  const remote = st.providers.filter((p) => p.configured);
  if (!remote.length) { box.innerHTML = '<p class="note">Aucun fournisseur distant configuré : tout passe par le modèle local.</p>'; return; }
  box.innerHTML = st.tasks.map((t) => {
    const order = remote.filter((p) => p.ranks[t]).sort((a, b) => a.ranks[t] - b.ranks[t]);
    const opts = `<option value="">Automatique${order[0] ? ` (${esc(order[0].name)})` : ""}</option>` +
      remote.map((p) => `<option value="${esc(p.id)}"${st.prefs[t] === p.id ? " selected" : ""}>${esc(p.name)} · ${esc(p.model)}</option>`).join("");
    return `<label class="us-pref"><span>${esc(TASK_LABELS[t] || t)}</span><select class="field" data-task="${esc(t)}">${opts}</select></label>`;
  }).join("");
  box.querySelectorAll("select").forEach((sel) => sel.onchange = async () => {
    const prefs = { ...st.prefs, [sel.dataset.task]: sel.value };
    if (!sel.value) delete prefs[sel.dataset.task];
    st.prefs = (await (await send_("/api/usage/routing", "PUT", { prefs })).json()).prefs;
    toast("Préférence de routage enregistrée.");
    sel.blur();
  });
}

$("usPeriod").querySelectorAll("button").forEach((b) => b.onclick = () => {
  usDays = +b.dataset.d;
  $("usPeriod").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
  usageOpen();
});
async function usageTry() {
  const msg = $("usTry").value.trim(); if (!msg) return;
  const r = await (await send_("/api/usage/route", "POST", { message: msg })).json();
  const head = `Type : <b>${esc(TASK_LABELS[r.task] || r.task)}</b> · ~${fmtN(r.est_tokens)} tokens · ` +
    (r.engine === "local" ? `réponse en <b>local</b>${r.reason ? " (" + esc(r.reason) + ")" : " (mode par défaut : local)"}` : "réponse par un <b>modèle distant</b>");
  $("usTryOut").innerHTML = `<p>${head}</p>` + (r.order.length ? `<ol>${r.order.map((o, i) =>
    `<li><b>${esc(o.name)}</b> <small>${esc(o.model)}</small>${i === 0 ? " — choisi" : " — relais"}${o.why.length ? `<small class="why">${esc(o.why.join(" · "))}</small>` : ""}</li>`).join("")}</ol>`
    : '<p class="note">Aucun fournisseur distant disponible.</p>');
}
$("usTryGo").onclick = usageTry;
$("usTry").addEventListener("keydown", (e) => { if (e.key === "Enter") usageTry(); });

// Branché sur les réglages : groupe « Connexions », chargé à l'ouverture de la rubrique, coupé à la fermeture.
SET_GROUPS.connections.push("usage");
PANE_TITLES.usage = "Consommation";
PANE_LOAD.usage = usageOpen;
document.querySelector('.pane[data-pane="usage"] .pane-title').textContent = "Consommation";
const _closeSettingsUsage = closeSettings;
closeSettings = function () { usageClose(); _closeSettingsUsage(); };   // le flux s'arrête avec les réglages

/* ============================================================
   TABLEAU DE BORD — Grafana intégré (servi par Atom sous /grafana/)
   ============================================================ */
let dashRange = "now-24h", dashOn = null;
const dashUrl = (kiosk = true) => `/grafana/d/atom/atom?orgId=1&from=${dashRange}&to=now&refresh=30s` +
  `&theme=${document.documentElement.dataset.theme === "light" ? "light" : "dark"}${kiosk ? "&kiosk" : ""}`;
async function loadDashboard() {
  if (dashOn === null) {
    try { dashOn = (await getJSON("/api/monitoring")).grafana; } catch { dashOn = false; }
  }
  $("dashFrame").hidden = !dashOn; $("dashOff").hidden = dashOn; $("dashOpen").hidden = !dashOn; $("dashRange").hidden = !dashOn;
  $("dashCheck").hidden = !dashOn; if (!dashOn) $("dashReport").hidden = true;
  if (!dashOn) {
    $("dashSrc").textContent = "";
    $("dashOff").innerHTML = `<div class="dash-off-card">${icon("pulse")}<h3>Tableau de bord Grafana</h3>
      <p>Graphiques de la consommation des modèles, des fournisseurs, du serveur et de la base, sur des heures ou des semaines.</p>
      <p>Pour l'activer, dans le fichier <code>.env</code> du serveur :</p>
      <pre>COMPOSE_FILE=docker-compose.yml:docker-compose.monitoring.yml
ATOM_METRICS_TOKEN=…   # openssl rand -hex 32</pre>
      <p>puis <code>./update.sh</code>. Grafana reste derrière ton mot de passe Atom : aucun port n'est ouvert.</p>
      <p class="note">En attendant, la consommation en direct est dans Réglages → Connexions → Consommation.</p>
      <button class="btn" data-goto-usage>Voir la consommation en direct</button></div>`;
    $("dashOff").querySelector("[data-goto-usage]").onclick = () => openSettings("usage");
    return;
  }
  $("dashSrc").textContent = "Grafana · Prometheus · actualisé toutes les 30 s";
  const want = dashUrl();
  if ($("dashFrame").dataset.src !== want) { $("dashFrame").src = want; $("dashFrame").dataset.src = want; }
}
$("dashRange").querySelectorAll("button").forEach((b) => b.onclick = () => {
  dashRange = b.dataset.r;
  $("dashRange").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
  loadDashboard();
});
$("dashOpen").onclick = () => window.open(dashUrl(false), "_blank", "noopener");
// Le thème d'Atom change : Grafana suit.
new MutationObserver(() => { if (currentView === "dash" && dashOn) loadDashboard(); })
  .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

/* ---- alertes (rubrique Consommation) */
function renderAlerts() {
  const a = usState?.alerts; if (!a) return;
  const budget = a.budget ? `${fmtCost(a.month_cost)} dépensés ce mois sur ${fmtCost(a.budget)}` : "aucun budget fixé (ATOM_COST_BUDGET)";
  $("alInfo").innerHTML = `Atom te prévient sur ton téléphone quand un quota atteint <b>${Math.round(a.quota_threshold * 100)} %</b>, quand tous les fournisseurs distants sont en panne, et quand le budget du mois est atteint (${esc(budget)}).`;
  $("alList").innerHTML = a.history.length ? a.history.map((h) =>
    `<li><small>${esc(new Date(h.at * 1000).toLocaleString("fr-FR"))}</small><b>${esc(h.title)}</b> — ${esc(h.body)}</li>`).join("")
    : '<li class="none">Aucune alerte envoyée pour l\'instant.</li>';
}
$("alTest").onclick = async () => {
  const r = await (await send_("/api/alerts/test", "POST")).json();
  toast(r.sent ? "Notification d'essai envoyée." : "Aucun canal configuré (ntfy ou Telegram) : voir le README.");
};
const _renderUsageAlerts = renderUsage;
renderUsage = function (freshId) { _renderUsageAlerts(freshId); renderAlerts(); };

/* Vérifier le tableau : chaque requête est exécutée à travers Grafana, les erreurs exactes sont listées. */
$("dashCheck").onclick = async (e) => {
  const b = e.currentTarget, box = $("dashReport");
  b.disabled = true; b.innerHTML = '<span class="spin"></span> Vérification…';
  try {
    const r = await getJSON("/api/monitoring/check");
    const empty = r.empty?.length ? `<p class="note">Encore vides (normal tant qu'Atom n'a pas servi ces cas) : ${r.empty.map(esc).join(", ")}.</p>` : "";
    box.innerHTML = r.ok
      ? `<p><span class="st-dot ok"></span> Les ${r.checked} panneaux répondent sans erreur.</p>${empty}`
      : `<p><span class="st-dot error"></span> ${r.errors.length} erreur(s) sur ${r.checked} panneaux :</p><ul>${r.errors.map((x) =>
          `<li><b>${esc(x.panel)}</b> — <code>${esc(x.error)}</code></li>`).join("")}</ul>${empty}
         <button class="btn sm" data-copy-report>Copier le rapport</button>`;
    box.hidden = false;
    box.querySelector("[data-copy-report]")?.addEventListener("click", () => {
      copyText(r.errors.map((x) => `${x.panel} : ${x.error}`).join("\n")); toast("Rapport copié.");
    });
  } catch (err) { box.innerHTML = `<p class="us-ko">${esc(err.message)}</p>`; box.hidden = false; }
  finally { b.disabled = false; b.textContent = "Vérifier le tableau"; }
};

/* ---- Diagnostic complet (Réglages → État) */
let diagText = "";
$("diagGo").onclick = async (e) => {
  const b = e.currentTarget; b.disabled = true; b.innerHTML = '<span class="spin"></span> Diagnostic en cours…';
  try {
    const r = await (await send_("/api/diagnostic", "POST")).json();
    diagText = r.report;
    $("diagOut").textContent = r.report; $("diagOut").hidden = false; $("diagCopy").hidden = false;
    toast(r.status === "ok" ? "Tout fonctionne." : r.status === "warn" ? "Diagnostic terminé : quelques points à surveiller." : "Diagnostic terminé : des problèmes ont été détectés.");
  } catch (err) { toast(esc(err.message)); }
  finally { b.disabled = false; b.textContent = "Lancer le diagnostic"; }
};
$("diagCopy").onclick = () => { copyText(diagText); toast("Rapport copié : colle-le dans ta demande d'aide."); };
