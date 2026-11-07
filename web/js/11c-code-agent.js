"use strict";

/* Mode Code (suite) — voir 11a-code-explorateur.js. */
/* ---- agent : une tâche sur tout le projet, modifications validées à la fin */
let agRun = null;
const AG_ICON = { list: "folder", read: "doc", search: "search", edit: "edit", write: "plus", done: "check" };
function agOpen() {
  code.active = "__agent"; code.sel = null;
  renderTabs(); $("cvAgentView").hidden = false; $("cvMainWrap").hidden = true; cvStatusUpdate(); renderTree();
  const h = typeof hybridState !== "undefined" ? hybridState : null;
  const remoteOk = h?.configured && h?.allow_docs;
  $("agEngine").value = remoteOk ? "remote" : "local";
  $("agEngineNote").innerHTML = !h?.configured ? "Aucune API configurée : l'agent tournera en local (lent, moins fiable)."
    : !h.allow_docs ? 'Le code ne part pas vers l\'API tant que tu ne l\'autorises pas. <button class="btn sm" id="agAllow">Autoriser l\'envoi du code</button>' : "";
  $("agAllow")?.addEventListener("click", async () => {
    if (!confirm("Autoriser l'envoi de ta bibliothèque, de tes fichiers et de ton code aux API distantes ?\n\nSeuls les fournisseurs qui acceptent les données privées (pas Gemini ni OpenRouter) les recevront. Réglable dans Réglages → Connexions.")) return;
    await saveHybrid({ allow_docs: true }); agOpen(); toast("Envoi du code autorisé · l'agent utilisera l'API distante.");
  });
  $("agInfo").textContent = $("cvProject").selectedOptions[0]?.textContent || "";
  $("agClose").hidden = !code.open.length;
  loadAgHistory(); loadAgRules();
  const last = store.get(agKey(), null);
  if (last && (!agState || agState.id !== last)) agFollow(last, true);
  else if (!agRun) $("agTask").focus();
  saveCodeState();
}
function agClose() {
  const last = code.open.at(-1);
  if (!last) return;
  code.active = last.path; renderTabs(); renderEditor(); renderTree(); saveCodeState();
}
$("agClose").onclick = agClose;
$("agNew").onclick = () => { agReset(); agParent = null; $("agParentNote").hidden = true; store.set(agKey(), null); $("agTask").value = ""; $("agTask").focus(); loadAgHistory(); };
$("agParentCancel").onclick = () => { agParent = null; $("agParentNote").hidden = true; };
$("agTask").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("agRun").click(); });
function agStep(cls, ic, html) {
  const d = document.createElement("div"); d.className = "ag-step " + cls;
  d.innerHTML = `<span class="ic">${icon(ic)}</span><div>${html}</div>`;
  $("agLog").appendChild(d); $("agHome").hidden = true; d.scrollIntoView({ block: "nearest" });
  return d;
}
const agArgs = (t, a) => t === "read" ? `${a.path || ""}${a.start ? ` (l. ${a.start}${a.end ? "-" + a.end : ""})` : ""}` : t === "search" ? `« ${a.query || ""} »`
  : t === "list" ? (a.dir || "racine") : a.path || "";
const AG_VERB = { list: "Liste", read: "Lit", search: "Cherche", edit: "Modifie", write: "Écrit", done: "Terminé" };
// Les tâches tournent sur le serveur : la page ne fait que suivre (et peut être rechargée).
let agPoll = 0, agState = null;   // { id, after, first, lastAction, thinking }
const agKey = () => `agent:last:${code.project}`;
function agReset() { $("agLog").innerHTML = ""; $("agRes").hidden = true; agRun = null; agState = null; clearTimeout(agPoll); agHomeUpdate(); }
function agBusy(on) {
  const btn = $("agRun"); btn.textContent = on ? "Arrêter" : "Lancer"; btn.classList.toggle("primary", !on);
  if (on) { setEmotion("focus"); entity.scan = true; } else { setEmotion("idle"); entity.scan = false; }
}
function agHandle(ev, live) {
  const st = agState, proj = $("cvProject").selectedOptions[0]?.textContent || "";
  if (ev.type === "start") { $("agInfo").textContent = `${proj} · ${ev.info}`; agRun = { ...(agRun || {}), id: ev.id, writable: ev.writable }; }
  else if (ev.type === "engine") { $("agInfo").textContent = `${proj} · ${ev.name}`; }
  else if (ev.type === "thinking") { st.thinking?.remove(); st.thinking = live ? agStep("", "spark", '<span class="t"><span class="spin"></span> réfléchit…</span>') : null; if (live) entity.tokenKick = 1; }
  else if (ev.type === "thought") { st.thinking?.remove(); agStep("", "spark", `<span class="t">${esc(ev.text)}</span>`); }
  else if (ev.type === "action") {
    st.thinking?.remove();
    if (ev.thought) agStep(st.first ? "plan" : "", "spark", `<span class="t">${esc(ev.thought)}</span>`);
    st.first = false;
    if (ev.tool !== "done") {
      st.lastAction = agStep("", AG_ICON[ev.tool] || "spark", `<span class="a">${AG_VERB[ev.tool] || esc(ev.tool)} ${esc(agArgs(ev.tool, ev.args))}</span><div class="r"></div>`);
      st.lastAction.querySelector(".a").onclick = (e) => e.currentTarget.closest(".ag-step").classList.toggle("open");
      if (live && (ev.tool === "edit" || ev.tool === "write")) entity.absorb = 1;
    }
  } else if (ev.type === "result" && st.lastAction) {
    st.lastAction.querySelector(".r").textContent = ev.text; if (!ev.ok) st.lastAction.classList.add("ko");
  } else if (ev.type === "info") agStep("", "spark", `<span class="t">${esc(ev.message)}</span>`);
  else if (ev.type === "error") { st.thinking?.remove(); agStep("ko", "x", `<span class="t">${esc(ev.message)}</span>`); if (live) entity.glitch = 1; }
  else if (ev.type === "done") { st.thinking?.remove(); agRun = { ...(agRun || {}), id: ev.id, files: ev.files, summary: ev.summary, applied: ev.applied || [] }; agResults(); }
}
async function agFollow(rid, live = true) {
  clearTimeout(agPoll);
  if (!agState || agState.id !== rid) {
    $("agLog").innerHTML = ""; $("agRes").hidden = true;
    agState = { id: rid, after: 0, first: true };
  }
  let r;
  try { r = await getJSON(`/api/agent/runs/${rid}?after=${agState.after}`); }
  catch { agBusy(false); store.set(agKey(), null); return; }
  if (agState.after === 0) {
    agStep("plan", "users", `<span class="t"><b>${esc(r.task)}</b>${r.parent ? ' <span class="note">· suite d\'une tâche précédente</span>' : ""}</span>`);
  }
  for (const ev of r.events) agHandle(ev, live && r.status === "running");
  agState.after += r.events.length;
  const running = r.status === "running";
  agBusy(running);
  if (running) agPoll = setTimeout(() => agFollow(rid, true), 900);
  else {
    if (r.status === "interrupted") agStep("ko", "x", '<span class="t">Tâche interrompue par un redémarrage du serveur.</span>');
    if (r.status === "stopped" && !agRun?.files) agStep("ko", "x", '<span class="t">Arrêtée.</span>');
    loadAgHistory();
  }
}
$("agRun").onclick = async () => {
  if (agState && $("agRun").textContent === "Arrêter") { try { await send_(`/api/agent/runs/${agState.id}/stop`, "POST"); } catch {} return; }
  const task = $("agTask").value.trim();
  if (task.length < 3) { $("agTask").focus(); return; }
  agReset();
  try {
    const { id } = await (await send_(`/api/agent/${code.project}`, "POST", { task, engine: $("agEngine").value, parent: agParent || undefined, readonly: $("agReadonly").checked })).json();
    const wasFollowUp = !!agParent;
    agParent = null; $("agParentNote").hidden = true;
    store.set(agKey(), id); agBusy(true); await agFollow(id);
    if (wasFollowUp || CORRECTION.test(task)) agSuggestRule(task);
  } catch (e) { toast(`<b>Agent</b> · ${esc(e.message)}`); }
};
let agParent = null;
async function loadAgHistory() {
  const sel = $("agHistory");
  let d; try { d = await getJSON(`/api/agent/${code.project}/runs`); } catch { return; }
  const ST = { running: "en cours", done: "terminée", error: "erreur", stopped: "arrêtée", interrupted: "interrompue" };
  agHomeUpdate(d.runs);
  sel.innerHTML = '<option value="">Historique…</option>' + d.runs.map((r) =>
    `<option value="${r.id}" ${agState?.id === r.id ? "selected" : ""}>${esc(new Date(r.created_at * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }))} · ${esc(r.task.slice(0, 60))} · ${ST[r.status] || r.status}${r.files ? ` · ${r.files} fichier(s)` : ""}</option>`).join("");
  sel.hidden = !d.runs.length;
}
$("agHistory").onchange = (e) => { const id = e.target.value; if (!id) return; agReset(); store.set(agKey(), id); agFollow(id, true); };
function agContinue() {
  agParent = agRun?.id || null;
  $("agParentNote").hidden = !agParent;
  $("agTask").value = ""; $("agTask").placeholder = "Que doit faire l'agent ensuite ? Ex. « Ajoute maintenant des tests pour Parse »";
  $("agTask").focus(); $("agForm").scrollIntoView({ block: "nearest" });
}
function agResults() {
  const box = $("agRes"), r = agRun; box.hidden = false;
  if (!r.files?.length) {
    box.innerHTML = (r.summary ? `<h5>Réponse de l'agent</h5><div class="sum md"></div>` : "<h5>Aucune modification proposée</h5>")
      + `<p class="note">${r.applied?.length ? `Appliqué : ${esc(r.applied.join(", "))}. Pense au commit dans le panneau Git.` : "Aucun fichier modifié."}</p><div class="ag-acts"><button class="btn" id="agMore">Poursuivre…</button></div>`;
    if (r.summary) setMd(box.querySelector(".sum"), r.summary);
    $("agMore").onclick = agContinue;
    return;
  }
  const add = r.files.reduce((s, f) => s + f.added, 0), rem = r.files.reduce((s, f) => s + f.removed, 0);
  box.innerHTML = `<h5>${r.files.length} fichier${r.files.length > 1 ? "s" : ""} modifié${r.files.length > 1 ? "s" : ""} · +${add} / −${rem}</h5>
    ${r.summary ? `<div class="sum md">${md(r.summary)}</div>` : ""}
    ${r.files.map((f, i) => `<details class="ag-file"><summary><input type="checkbox" data-ag="${i}" checked><span>${esc(f.path)}</span>${f.new_file ? "<em>nouveau</em>" : ""}<em>+${f.added} −${f.removed}</em></summary>
      <div class="cv-diff">${f.diff.split("\n").filter((l, k) => !(k < 2 && (l.startsWith("---") || l.startsWith("+++")))).map((l) => `<div class="${l.startsWith("@@") ? "hunk" : l[0] === "+" ? "add" : l[0] === "-" ? "del" : ""}">${esc(l)}</div>`).join("")}</div></details>`).join("")}
    <div class="ag-acts">${r.writable !== false ? '<button class="btn primary" id="agApply">Appliquer la sélection</button>' : '<span class="note">Projet en lecture seule : télécharge le patch.</span>'}
      <button class="btn" id="agPatch">${icon("download")}Patch</button>${sbInfo?.enabled ? '<button class="btn" id="agTest">Tester ces modifications</button>' : ""}<button class="btn" id="agMore">Poursuivre…</button><button class="btn" id="agDrop">Abandonner</button></div>`;
  $("agMore").onclick = agContinue;
  if ($("agTest")) $("agTest").onclick = () => { let o = box.querySelector(".sb-out"); if (!o) { o = document.createElement("div"); o.className = "sb-out"; box.appendChild(o); } sbRun({ run_id: r.id }, o, $("agTest")); };
  box.querySelectorAll(".ag-file input").forEach((c) => { c.onclick = (e) => e.stopPropagation(); });
  const picked = () => [...box.querySelectorAll("[data-ag]:checked")].map((c) => r.files[+c.dataset.ag]);
  $("agPatch").onclick = () => downloadPatch(picked().map((f) => f.diff).join(""), "atom-agent.patch");
  $("agDrop").onclick = async () => {
    if (!confirm("Abandonner ces modifications et effacer cette tâche de l'historique ?")) return;
    try { await send_(`/api/agent/runs/${r.id}`, "DELETE"); } catch {}
    store.set(agKey(), null); agReset(); loadAgHistory();
  };
  if ($("agApply")) $("agApply").onclick = async () => {
    const files = picked(); if (!files.length) { toast("Coche au moins un fichier."); return; }
    try {
      const d = await (await send_(`/api/agent/runs/${r.id}/apply`, "POST", { paths: files.map((f) => f.path) })).json();
      toast(`${d.applied.length} fichier${d.applied.length > 1 ? "s" : ""} appliqué${d.applied.length > 1 ? "s" : ""}` + (d.conflicts.length ? ` · ${d.conflicts.length} en conflit (modifiés entre-temps) : ${esc(d.conflicts.join(", "))}` : "") + ". Pense au commit dans le panneau Git.");
      entity.seal = 1;
      code.open = code.open.filter((x) => !d.applied.includes(x.path));
      r.files = r.files.filter((f) => !d.applied.includes(f.path));
      r.applied = [...(r.applied || []), ...d.applied];
      agResults(); loadChanges(); setTimeout(loadCodeFiles, 1500); saveCodeState();
    } catch (e) { toast(`<b>Agent</b> · ${esc(e.message)}`); }
  };
}
