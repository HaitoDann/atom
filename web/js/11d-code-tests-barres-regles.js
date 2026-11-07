"use strict";

/* Mode Code (suite) — voir 11a-code-explorateur.js. */
/* ---- bac à sable : lancer les tests dans un conteneur jetable */
let sbInfo = null;
async function loadSandbox() {
  try { sbInfo = await getJSON(`/api/sandbox/${code.project}`); } catch { sbInfo = null; $("cvTests").hidden = true; return; }
  $("cvTests").hidden = false;
  $("sbCmd").textContent = sbInfo.enabled ? (sbInfo.command || "commande à préciser") : "bac à sable désactivé";
  $("sbCmd").title = sbInfo.enabled ? sbInfo.command : sbInfo.reason;
  $("sbRun").hidden = !sbInfo.enabled; $("sbEdit").hidden = !sbInfo.enabled;
  if (!sbInfo.enabled) $("sbOut").innerHTML = `<div class="st">${esc(sbInfo.reason)} — voir le README, section « Bac à sable ».</div>`;
}
$("sbEdit").onclick = () => {
  const inp = $("sbCmdIn");
  if (inp.hidden) { inp.value = sbInfo?.command || ""; inp.hidden = false; $("sbCmd").hidden = true; inp.focus(); $("sbEdit").textContent = "enregistrer"; return; }
  send_(`/api/sandbox/${code.project}`, "PUT", { command: inp.value }).then((r) => r.json()).then((d) => { sbInfo = d; loadSandbox(); toast("Commande de test enregistrée."); }).catch((e) => toast(esc(e.message)));
  inp.hidden = true; $("sbCmd").hidden = false; $("sbEdit").textContent = "modifier";
};
$("sbCmdIn").addEventListener("keydown", (e) => { if (e.key === "Enter") $("sbEdit").click(); if (e.key === "Escape") { $("sbCmdIn").hidden = true; $("sbCmd").hidden = false; $("sbEdit").textContent = "modifier"; } });
async function sbRun(body, out, btn) {
  if (btn.disabled) return;
  const label = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Tests…';
  out.innerHTML = ""; setEmotion("focus"); entity.scan = true;
  const add = (cls, html) => { const d = document.createElement("div"); d.className = cls; d.innerHTML = html; out.appendChild(d); return d; };
  try {
    const r = await api(`/api/sandbox/${code.project}/run`, { method: "POST", body: JSON.stringify(body) });
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true }); let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === "step") add("st", esc(ev.message));
        else if (ev.type === "result") {
          out.querySelectorAll(".st").forEach((x) => x.remove());
          const ok = ev.code === 0;
          add("res " + (ok ? "ok" : "ko"), ok ? `✓ Tests réussis · ${ev.duration} s` : ev.code === -1 ? "Bac à sable indisponible" : `✗ Échec (code ${ev.code}) · ${ev.duration} s`);
          add("", `<pre>${esc((ev.output || "").replace(/\x1b\[[0-9;]*m/g, "") || "(aucune sortie)")}</pre>`);
          if (ok) entity.seal = 1; else entity.glitch = 1;
          if (ev.code !== -1 && !body.run_id) { sbLast = { ok }; cvStatusUpdate(); }
        }
      }
    }
  } catch (e) { add("res ko", esc(e.message)); }
  finally { btn.disabled = false; btn.innerHTML = label; setEmotion("idle"); entity.scan = false; }
}
$("sbRun").onclick = () => sbRun({}, $("sbOut"), $("sbRun"));

/* ---- barre d'activité, barre d'état, ouverture rapide (inspiré de VS Code / Zed) */
let cvPane = "files";
const PANE_NAMES = { files: "Fichiers", search: "Recherche dans le code", git: "Git", tests: "Tests" };
function cvSetPane(name) {
  cvPane = PANE_NAMES[name] ? name : "files";
  document.querySelector(".cv-side").dataset.show = cvPane;
  document.querySelectorAll("#cvRail button").forEach((b) => b.classList.toggle("on", b.dataset.pane === cvPane));
  $("cvPaneTitle").textContent = PANE_NAMES[cvPane];
  const grep = cvPane === "search";
  if (code.grep !== grep) { code.grep = grep; $("cvFilter").value = ""; }
  $("cvFilter").placeholder = grep ? "Texte à chercher dans tous les fichiers…" : "Filtrer par nom de fichier…";
  if (cvPane === "files" || cvPane === "search") { renderTree(); setTimeout(() => $("cvFilter").focus(), 0); }
  $("cvGitNote").hidden = !!code.git;
  saveCodeState();
}
document.querySelectorAll("#cvRail button").forEach((b) => { b.onclick = () => cvSetPane(b.dataset.pane); });
document.querySelector(".cv-side").dataset.show = "files";
let sbLast = null;   // dernier résultat de tests
function cvStatusUpdate() {
  const g = code.git;
  $("stBranch").innerHTML = g ? `<span class="lnk" data-go="git">⎇ ${esc(g.branch)}</span>` : "";
  const n = g?.files.length || 0;
  $("stChanges").innerHTML = g ? `<span class="lnk" data-go="git">${n ? `${n} modif.` : "propre"}${g.ahead ? ` · ↑${g.ahead}` : ""}</span>` : "";
  $("stTests").innerHTML = sbLast ? `<span class="lnk ${sbLast.ok ? "ok" : "ko"}" data-go="tests">${sbLast.ok ? "✓ tests" : "✗ tests"}</span>` : "";
  $("railGitDot").hidden = !n;
  $("railTestDot").hidden = !sbLast; $("railTestDot").classList.toggle("ko", !!sbLast && !sbLast.ok);
  const f = code.open.find((x) => x.path === code.active);
  $("stFile").textContent = f ? `${f.path} · ${f.content.split("\n").length} lignes · ${LANG(f.path).toUpperCase()}${code.sel ? ` · sél. ${code.sel[0]}-${code.sel[1]}` : ""}` : (code.active === "__agent" ? "Agent" : "");
  $("cvStatus").querySelectorAll("[data-go]").forEach((x) => { x.onclick = () => cvSetPane(x.dataset.go); });
}
// Ouverture rapide : recherche floue sur le nom et le chemin
let qoSel = 0, qoItems = [];
function qoScore(q, path) {
  const name = path.split("/").pop().toLowerCase(), p = path.toLowerCase();
  if (!q) return 1;
  if (name.startsWith(q)) return 100 - name.length / 100;
  if (name.includes(q)) return 80 - name.indexOf(q);
  if (p.includes(q)) return 50 - p.indexOf(q) / 10;
  let i = 0; for (const ch of p) if (ch === q[i]) i++;
  return i === q.length ? 20 - p.length / 100 : 0;
}
function qoRender() {
  const q = $("qoIn").value.trim().toLowerCase();
  const recent = code.open.map((f) => f.path).reverse();
  qoItems = (q ? code.files.map((f) => f.path) : [...new Set([...recent, ...code.files.map((f) => f.path)])])
    .map((p) => [p, qoScore(q, p) + (recent.includes(p) ? 5 : 0)]).filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 40).map((x) => x[0]);
  qoSel = Math.min(qoSel, Math.max(0, qoItems.length - 1));
  $("qoList").innerHTML = qoItems.map((p, i) => {
    const name = p.split("/").pop(), dir = p.slice(0, -name.length);
    const k = q ? name.toLowerCase().indexOf(q) : -1;
    const nm = k >= 0 ? esc(name.slice(0, k)) + `<b>${esc(name.slice(k, k + q.length))}</b>` + esc(name.slice(k + q.length)) : esc(name);
    return `<button data-i="${i}" class="${i === qoSel ? "on" : ""}"><span>${nm}</span><small>${esc(dir)}</small></button>`;
  }).join("") || '<p class="note" style="padding:8px">Aucun fichier.</p>';
  $("qoList").querySelectorAll("button").forEach((b) => { b.onclick = () => qoPick(+b.dataset.i); });
}
function qoOpen() { if (!code.project) return; $("quickOpen").hidden = false; $("qoIn").value = ""; qoSel = 0; qoRender(); $("qoIn").focus(); }
function qoClose() { $("quickOpen").hidden = true; }
function qoPick(i) { const p = qoItems[i]; qoClose(); if (p) openFile(p); }
$("qoIn").oninput = () => { qoSel = 0; qoRender(); };
$("qoIn").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { qoSel = Math.min(qoItems.length - 1, qoSel + 1); qoRender(); e.preventDefault(); }
  else if (e.key === "ArrowUp") { qoSel = Math.max(0, qoSel - 1); qoRender(); e.preventDefault(); }
  else if (e.key === "Enter") qoPick(qoSel);
  else if (e.key === "Escape") qoClose();
});
$("quickOpen").onclick = (e) => { if (e.target.id === "quickOpen") qoClose(); };
$("stQuick").onclick = qoOpen;
document.addEventListener("keydown", (e) => {
  if ($("codeView").hidden) return;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && !e.shiftKey && e.key.toLowerCase() === "p") { e.preventDefault(); qoOpen(); }
  else if (mod && e.shiftKey && e.key.toLowerCase() === "f") { e.preventDefault(); cvSetPane("search"); }
  else if (mod && e.shiftKey && e.key.toLowerCase() === "g") { e.preventDefault(); cvSetPane("git"); }
  else if (mod && e.key === "Enter" && code.active === "__agent" && document.activeElement !== $("agTask")) { e.preventDefault(); $("agTask").focus(); }
});
// Accueil de l'agent : idées de tâches et tâches récentes
const AG_IDEAS = [
  ["Expliquer le projet", "Explique-moi ce projet : à quoi il sert, son architecture, les fichiers clés et comment ils s'articulent."],
  ["Trouver des bugs", "Relis le code et trouve les bugs probables ou les cas non gérés. Pour chacun : fichier, ligne, risque, et propose une correction."],
  ["Ajouter des tests", "Ajoute des tests unitaires pour les fonctions principales qui n'en ont pas, puis lance-les."],
  ["Documenter", "Ajoute des commentaires de documentation sur les fonctions publiques qui n'en ont pas, sans changer le code."],
  ["Gestion des erreurs", "Repère les erreurs ignorées ou mal remontées et améliore leur gestion, sans changer le comportement normal."],
  ["Mettre à jour le README", "Mets à jour le README : présentation, installation, utilisation, structure du projet — d'après le code actuel."],
  ["Sécurité", "Fais une revue de sécurité du projet (entrées non validées, secrets, exécution de commandes, chemins) et propose des corrections."],
];
$("agChips").innerHTML = AG_IDEAS.map(([t], i) => `<button data-k="${i}">${esc(t)}</button>`).join("");
$("agChips").querySelectorAll("button").forEach((b) => { b.onclick = () => { $("agTask").value = AG_IDEAS[+b.dataset.k][1]; $("agTask").focus(); }; });
function agHomeUpdate(runs) {
  const showing = !!$("agLog").children.length;
  $("agHome").hidden = showing;
  if (!runs) return;
  const ST = { running: "en cours", done: "terminée", error: "erreur", stopped: "arrêtée", interrupted: "interrompue" };
  const list = runs.slice(0, 6);
  $("agRecentTitle").hidden = !list.length;
  $("agRecent").innerHTML = list.map((r) => `<button data-id="${esc(r.id)}"><span class="t">${esc(r.task)}</span><small>${esc(ST[r.status] || r.status)}</small>
    <small class="t">${esc(r.summary || "")}</small><small>${new Date(r.created_at * 1000).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })}${r.files ? ` · ${r.files} fichier(s)` : ""}</small></button>`).join("");
  $("agRecent").querySelectorAll("button").forEach((b) => { b.onclick = () => { agReset(); store.set(agKey(), b.dataset.id); agFollow(b.dataset.id, true); }; });
}

/* ---- règles retenues par projet (comme les règles de Cursor) */
let agRules = [];
async function loadAgRules() {
  try { agRules = (await getJSON(`/api/agent/${code.project}/rules`)).rules; } catch { agRules = []; }
  $("agRules").innerHTML = agRules.length ? agRules.map((r, i) => `<div><span>${esc(r)}</span><button data-rm="${i}" title="Supprimer">retirer</button></div>`).join("")
    : '<p class="note" style="margin:0">Aucune règle. Quand tu corriges l\'agent (« utilise plutôt… », « jamais… »), il te propose de la retenir.</p>';
  $("agRules").querySelectorAll("[data-rm]").forEach((b) => { b.onclick = () => saveAgRules(agRules.filter((_, i) => i !== +b.dataset.rm)); });
}
async function saveAgRules(list) {
  try { agRules = (await (await send_(`/api/agent/${code.project}/rules`, "PUT", { rules: list })).json()).rules; } catch (e) { toast(esc(e.message)); }
  loadAgRules();
}
$("agRuleAdd").onclick = () => { const v = $("agRuleIn").value.trim(); if (!v) return; $("agRuleIn").value = ""; saveAgRules([...agRules, v]); toast("Règle ajoutée au projet."); };
$("agRuleIn").addEventListener("keydown", (e) => { if (e.key === "Enter") $("agRuleAdd").click(); });
// Une correction ressemble souvent à une règle durable : on propose de la retenir.
const CORRECTION = /\b(toujours|jamais|ne (?:pas|plus|jamais)|n'utilise|utilise plutôt|plutôt que|au lieu de|on utilise|je préfère|préfère|évite|interdit|convention|style)\b/i;
function agSuggestRule(task) {
  const sentence = task.split(/(?<=[.!?])\s+/).find((x) => CORRECTION.test(x));
  if (!sentence || agRules.includes(sentence.trim())) return;
  const d = agStep("plan", "check", `<span class="t">Retenir comme règle du projet ? « ${esc(sentence.trim())} » <button class="btn sm" data-keep>Retenir</button></span>`);
  d.querySelector("[data-keep]").onclick = (e) => { saveAgRules([...agRules, sentence.trim()]); e.currentTarget.replaceWith(document.createTextNode("✓ retenue")); };
}
