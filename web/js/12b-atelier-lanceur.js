"use strict";

/* ============================================================
   LANCEUR D'ATELIER — une demande, un schéma, une équipe, un clic
   ============================================================ */
// S'ouvre depuis la barre latérale, le bouton sous la saisie, le menu « + » ou la palette (Ctrl+K).
// L'équipe et les étapes sont recalculées par le serveur à chaque choix (/api/workshop/preview), sans rien envoyer.
const WL_PATTERNS = {
  review: { flow: ["Rédacteur", "Relecteur", "Correction"], arrow: "→", d: "Un modèle rédige, un autre le relit avec une grille stricte, puis la version est corrigée. Idéal pour du code ou un texte soigné." },
  panel: { flow: ["A", "B", "Arbitre"], arrow: "⇢", d: "Deux modèles répondent chacun de leur côté, un arbitre compare et fait la synthèse. Idéal pour analyser ou comparer." },
  debate: { flow: ["Pour", "Contre", "Arbitre"], arrow: "⇄", d: "Deux modèles défendent des positions opposées, un arbitre tranche. Idéal pour une décision." },
};
let wl = { pattern: null, participants: null, rounds: 1, touched: false, preview: null, timer: 0, options: [], fresh: true };
// Couleur de chaque fournisseur : la même que dans le tableau de bord Grafana.
const PROV_COLORS = { local: "#cfcfcf", groq: "#f2a65a", gemini: "#7aa6f0", openrouter: "#b48cf2", mistral: "#f28c8c",
  cerebras: "#6fcf97", github: "#9aa0a6", openai: "#5ec8c8", deepseek: "#7f8cf0" };
const provColor = (engine) => PROV_COLORS[(engine || "").split(/[ ·]/)[0].toLowerCase()] || "#9aa0a6";

async function openWsLauncher(text = "") {
  // Affiché tout de suite (réactif), rempli dès que la configuration arrive.
  $("wlText").value = text || $("wlText").value || "";
  $("wlGo").disabled = true;
  $("wsLaunch").hidden = false;
  document.body.classList.add("wl-open");
  try { workshopCfg = await getJSON("/api/workshop"); } catch (e) { toast(esc(e.message)); closeWsLauncher(); return; }
  // Fermer puis rouvrir garde tes choix (méthode, équipe, options) tant que l'atelier n'a pas été lancé.
  if (wl.fresh) {
    wl = { pattern: workshopCfg.pattern, participants: [...workshopCfg.participants], rounds: workshopCfg.rounds, touched: false,
           preview: null, timer: 0, options: workshopCfg.options, architect: workshopCfg.architect || "auto", fresh: false };
  } else wl.options = workshopCfg.options;
  await wlRefresh();
  requestAnimationFrame(() => { $("wlText").focus(); $("wlText").setSelectionRange($("wlText").value.length, $("wlText").value.length); });
}
function closeWsLauncher() { $("wsLaunch").hidden = true; document.body.classList.remove("wl-open"); }

async function wlRefresh() {
  let r;
  try {
    r = await (await send_("/api/workshop/preview", "POST",
      { message: $("wlText").value, pattern: wl.pattern, participants: wl.participants, rounds: wl.rounds, architect: wl.architect })).json();
  } catch (e) { $("wlWarn").textContent = e.message; $("wlWarn").hidden = false; return; }
  // Tant que tu n'as pas choisi toi-même, le schéma suit la suggestion d'Atom.
  if (!wl.touched && $("wlText").value.trim() && r.suggested !== wl.pattern) { wl.pattern = r.suggested; return wlRefresh(); }
  wl.preview = r;
  wlRender();
}
const wlRefreshSoon = () => { clearTimeout(wl.timer); wl.timer = setTimeout(wlRefresh, 350); };

function wlRender() {
  const r = wl.preview; if (!r) return;
  // Exemples (une fois)
  if (!$("wlEx").children.length) {
    $("wlEx").innerHTML = '<span class="wl-ex-t">Essayer :</span>' + r.examples.map((x, i) => `<button type="button" data-ex="${i}">${esc(x.title)}</button>`).join("");
    $("wlEx").querySelectorAll("[data-ex]").forEach((b) => b.onclick = () => {
      const x = r.examples[+b.dataset.ex]; $("wlText").value = x.text; wl.pattern = x.pattern; wl.touched = true; wlRefresh(); $("wlText").focus();
    });
  }
  // Schémas
  $("wlPatterns").innerHTML = Object.entries(WL_PATTERNS).map(([k, p]) => {
    const on = k === r.pattern, sug = k === r.suggested && $("wlText").value.trim();
    const flow = p.flow.map((x) => `<span>${esc(x)}</span>`).join(`<em>${p.arrow}</em>`);
    return `<button type="button" class="wl-pat${on ? " on" : ""}" role="radio" aria-checked="${on}" data-p="${k}">
      <span class="wl-radio" aria-hidden="true"></span>
      <span class="wl-pat-t"><b>${esc(workshopCfg.patterns[k])}</b>${sug ? '<span class="wl-sug">Conseillé</span>' : ""}</span>
      <small>${esc(p.d)}</small><span class="wl-mini">${flow}</span></button>`;
  }).join("");
  $("wlPatterns").querySelectorAll("[data-p]").forEach((b) => b.onclick = () => { wl.pattern = b.dataset.p; wl.touched = true; wlRefresh(); });
  $("wlHint").textContent = $("wlText").value.trim() ? `Conseil d'Atom : ${r.suggested_name.toLowerCase()} — ${r.suggested_reason}.` : "";

  // Équipe : un rôle par participant (Automatique = Atom choisit selon la force et la famille des modèles)
  const firstOf = {};
  r.steps.forEach((st) => { if (!(st.role in firstOf)) firstOf[st.role] = st; });
  const roles = r.roles;
  $("wlTeam").innerHTML = roles.map((role, i) => {
    const cur = wl.participants[i] || "auto";
    const shown = firstOf[role] || (role === "Correction" ? firstOf["Rédacteur"] : null);
    const opts = wl.options.map((o) => `<option value="${esc(o.id)}"${o.id === cur ? " selected" : ""}>${esc(o.id === "auto" && shown ? `Automatique · ${shown.engine}` : o.label)}</option>`).join("");
    return `<div class="wl-member" style="--pc:${provColor(shown?.engine)}">
      <span class="wl-dot" aria-hidden="true"></span>
      <span class="wl-mrole"><b>${esc(role)}</b>${shown ? `<small>${esc(shown.family)}${shown.remote ? "" : " · local"}</small>` : ""}</span>
      <select class="field" data-slot="${i}" aria-label="Modèle pour le rôle ${esc(role)}">${opts}</select></div>`;
  }).join("");
  $("wlTeam").querySelectorAll("select").forEach((sel) => sel.onchange = () => { wl.participants[+sel.dataset.slot] = sel.value; wlRefresh(); });

  // Architecte : un modèle fort transforme la demande en cahier des charges avant que les autres travaillent.
  $("wlArch").querySelectorAll("button").forEach((b) => { b.classList.toggle("on", b.dataset.a === wl.architect); b.setAttribute("aria-checked", b.dataset.a === wl.architect);
    b.onclick = () => { wl.architect = b.dataset.a; wlRefresh(); }; });
  $("wlArchNote").textContent = r.architect_active ? "cahier des charges d'abord" : wl.architect === "auto" ? "seulement pour code et pages web" : "";
  $("wlRoundsRow").hidden = r.pattern !== "review";
  $("wlRounds").querySelectorAll("button").forEach((b) => { b.classList.toggle("on", +b.dataset.r === r.rounds); b.onclick = () => { wl.rounds = +b.dataset.r; wlRefresh(); }; });

  // Étapes prévues, dans l'ordre
  $("wlFlow").innerHTML = r.steps.map((st) => `<li class="ws-node pending" style="--pc:${provColor(st.engine)}"><b>${esc(st.role)}</b><small>${esc(st.engine)}</small></li>`).join("");
  $("wlWarn").innerHTML = r.warnings.map((w) => `⚠ ${esc(w)}`).join("<br>");
  $("wlWarn").hidden = !r.warnings.length;
  const remote = r.remote_calls ? `${r.remote_calls} vers des API` : "tout en local";
  $("wlSum").innerHTML = `<span><b>${r.calls} appels</b> · ${remote}</span>${r.pattern === "review" ? '<small>La correction est sautée si la relecture est favorable.</small>' : ""}`;
  $("wlGo").disabled = !$("wlText").value.trim();
}

async function wlLaunch() {
  const text = $("wlText").value.trim(), r = wl.preview;
  if (!text || !r || busy) return;
  if ($("wlKeep").checked) saveWorkshop({ pattern: r.pattern, participants: wl.participants, rounds: r.rounds, architect: wl.architect });
  closeWsLauncher();
  if (currentView !== "chat") showView("chat");
  input.value = ""; autoGrow();
  $("wlText").value = ""; wl.fresh = true;
  sendWorkshop(text, { pattern: r.pattern, participants: wl.participants, rounds: r.rounds, architect: wl.architect });
}

$("wlText").addEventListener("input", () => { $("wlGo").disabled = !$("wlText").value.trim(); wlRefreshSoon(); });
$("wlText").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); wlLaunch(); } });
$("wlGo").onclick = wlLaunch;
$("wlClose").onclick = closeWsLauncher;
// Pas de fermeture au clic à côté (trop de fermetures involontaires) : croix ou Échap, et ta demande est conservée.
$("wsLaunch").addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); closeWsLauncher(); } });
$("navWs").onclick = () => openWsLauncher(input.value);
