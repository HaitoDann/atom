"use strict";

/* ============================================================
   ATELIER MULTI-IA
   ============================================================ */
let workshopCfg = null, workshopNext = false, remoteModels = [];
async function loadWorkshop() {
  try { workshopCfg = await getJSON("/api/workshop"); } catch { return; }
  $("wsBtn").style.display = workshopCfg.enabled ? "" : "none";
  if (!workshopCfg.enabled && workshopNext) { workshopNext = false; }
  $("wsBtn").classList.toggle("on", workshopNext);
  $("wsEnabled").checked = workshopCfg.enabled;
  $("wsPattern").innerHTML = "";
  for (const [k, label] of Object.entries(workshopCfg.patterns)) {
    const b = document.createElement("button");
    b.className = "btn" + (workshopCfg.pattern === k ? " primary" : "");
    b.textContent = label; b.onclick = () => saveWorkshop({ pattern: k });
    $("wsPattern").appendChild(b);
  }
  const opts = workshopCfg.options.map((o) => [o.id, o.label + (o.family ? ` · ${o.family}` : "")]);
  const roles = workshopCfg.roles[workshopCfg.pattern];
  $("wsParts").innerHTML = "";
  roles.forEach((role, i) => {
    const row = document.createElement("div"); row.className = "row"; row.style.margin = "6px 0";
    const cur = workshopCfg.participants[i] || "auto";
    row.innerHTML = `<span style="width:130px;font-size:13px;color:var(--text-2)">${esc(role)}</span>`;
    const sel = document.createElement("select"); sel.className = "field"; sel.style.cssText = "flex:1;min-width:0;max-width:260px";
    sel.innerHTML = opts.map(([v, t]) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(t)}</option>`).join("")
      + (opts.some(([v]) => v === cur) ? "" : `<option selected value="${esc(cur)}">${esc(cur)}</option>`);
    sel.onchange = () => { const p = [...workshopCfg.participants]; p[i] = sel.value; saveWorkshop({ participants: p }); };
    row.appendChild(sel);
    const eff = document.createElement("span"); eff.className = "note"; eff.style.cssText = "margin-left:8px;white-space:nowrap";
    if (cur === "auto") eff.textContent = "→ " + (workshopCfg.assigned[i] || "");
    row.appendChild(eff);
    $("wsParts").appendChild(row);
  });
  $("wsWarn").innerHTML = workshopCfg.warnings.map((w) => `⚠ ${esc(w)}`).join("<br>");
  $("wsWarn").hidden = !workshopCfg.warnings.length;
  $("wsRoundsRow").hidden = workshopCfg.pattern !== "review";
  $("wsRounds").value = workshopCfg.rounds;
  const n = workshopCfg.pattern === "review" ? 1 + 2 * workshopCfg.rounds : 3;
  const remote = (workshopCfg.pattern === "review"
    ? [workshopCfg.assigned[0], ...Array(workshopCfg.rounds).fill(0).flatMap(() => [workshopCfg.assigned[1], workshopCfg.assigned[2]])]
    : workshopCfg.assigned.slice(0, 3)).filter((p) => !p.startsWith("Local")).length;
  $("wsCost").textContent = `Jusqu'à ${n} étapes par demande, dont ${remote} via des API distantes. Compte jusqu'à ${n}× le temps d'une réponse normale`
    + (workshopCfg.pattern === "review" ? " — si la relecture ne trouve rien d'important, la correction est sautée." : ".");
}
async function saveWorkshop(patch) {
  try { await api("/api/workshop", { method: "PUT", body: JSON.stringify(patch) }); } catch (e) { toast(esc(e.message)); }
  loadWorkshop();
}
$("wsEnabled").onchange = () => saveWorkshop({ enabled: $("wsEnabled").checked });
$("wsRounds").onchange = () => saveWorkshop({ rounds: +$("wsRounds").value });
$("wsBtn").onclick = () => { workshopNext = !workshopNext; $("wsBtn").classList.toggle("on", workshopNext); input.focus(); };

function workshopEl(w) {
  const d = document.createElement("details");
  d.className = "ws";
  d.innerHTML = `<summary>${icon("users")}Atelier · ${esc(w.name)} · ${w.steps.length} étape${w.steps.length > 1 ? "s" : ""} avant la réponse</summary>`;
  for (const s of w.steps) {
    const c = document.createElement("div"); c.className = "ws-step";
    c.innerHTML = `<div class="ws-h"><b>${esc(s.role)}</b><span>${esc(s.engine)}</span></div><div class="md"></div>`;
    setMd(c.querySelector(".md"), s.text);
    d.appendChild(c);
  }
  return d;
}

async function sendWorkshop(text) {
  exitHero();
  workshopNext = false; $("wsBtn").classList.remove("on");
  $("empty")?.remove();
  setBusy(true);
  const userMsg = { role: "user", content: text };
  history.push(userMsg);
  chat.appendChild(msgEl(userMsg, history.length - 1));
  setEmotion("focus"); setEntityState("atelier…");
  const el = document.createElement("div");
  el.className = "msg atom";
  el.innerHTML = `<details class="ws" open><summary>${icon("users")}Atelier en cours…</summary><div class="ws-live"></div></details><div class="body md"></div>`;
  chat.appendChild(el); scroller.scrollTop = scroller.scrollHeight;
  const live = el.querySelector(".ws-live"), body = el.querySelector(".body"), sum = el.querySelector("summary");
  const steps = []; let final = "", asstId = null, q = false;
  controller = new AbortController();
  try {
    const r = await api("/api/workshop/run", { method: "POST", signal: controller.signal,
      body: JSON.stringify({ message: text, conversation_id: settings.conversationId }) });
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
        if (ev.type === "meta") { if (settings.conversationId !== ev.conversation_id) { settings.conversationId = ev.conversation_id; saveSettings(); loadConversations(); } }
        else if (ev.type === "ids") { userMsg.id = ev.user_id; }
        else if (ev.type === "step" && ev.status === "start") {
          sum.innerHTML = `${icon("users")}Atelier · ${esc(ev.role)} (${esc(ev.engine)})…`;
          entity.tokenKick = 1;
          if (ev.final) { entity.split = 0; entity.rippleT = 0; entity.remote = false; }
          else { entity.split = 2; entity.activeCluster = ev.index; entity.remote = /^(?!Local)/.test(ev.engine); }
          if (!ev.final) {
            const c = document.createElement("div"); c.className = "ws-step";
            c.innerHTML = `<div class="ws-h"><b>${esc(ev.role)}</b><span>${esc(ev.engine)}</span></div><div class="md"><span class="live"><span class="mini"></span><span>écrit…</span></span></div>`;
            live.appendChild(c); steps[ev.index] = { el: c, text: "" };
          } else { body.innerHTML = '<span class="live"><span class="mini"></span><span>Rédaction de la réponse finale…</span></span>'; setEmotion("talking"); }
        } else if (ev.type === "step" && ev.status === "token") {
          const s = steps[ev.index]; if (!s) continue; s.text += ev.text;
          if (!q) { q = true; requestAnimationFrame(() => { q = false; steps.forEach((x) => x && (x.el.querySelector(".md").innerHTML = md(x.text))); }); }
        } else if (ev.type === "step" && ev.status === "engine") {
          const s = steps[ev.index]; if (s) { const sp = s.el.querySelector(".ws-h span"); sp.textContent = ev.engine; sp.title = ev.reason || ""; }
          if (ev.reason) toast(`<b>Atelier</b> · relais : ${esc(ev.reason)}`);
        } else if (ev.type === "step" && ev.status === "done") {
          const s = steps[ev.index]; if (s) { s.text = ev.text; setMd(s.el.querySelector(".md"), ev.text); }
        } else if (ev.type === "token") {
          final += ev.text; entity.tokenKick = 1;
          body.innerHTML = md(final); body.lastElementChild?.classList.add("cursor");
          if (atBottom()) scroller.scrollTop = scroller.scrollHeight;
        } else if (ev.type === "done") { asstId = ev.id; final = ev.final; }
        else if (ev.type === "error") throw new Error(ev.message);
      }
    }
    entity.split = 0; entity.remote = false;
    setBusy(false);
    await openConversation(settings.conversationId);
    setEmotion("joy");
  } catch (err) {
    entity.split = 0; entity.remote = false; entity.glitch = 1;
    setBusy(false);
    if (err.name === "AbortError") { toast("Atelier arrêté."); await openConversation(settings.conversationId); }
    else { el.replaceWith(msgEl({ role: "assistant", content: err.message, error: true }, -1)); setEmotion("fear"); }
  } finally {
    controller = null; setBusy(false); scheduleRest(); loadConversations();
  }
}

/* ============================================================
   ESPACES — conversations, consignes et documents par sujet
   ============================================================ */
let spacesList = [], spEditing = null;
const activeSpace = () => spacesList.find((x) => x.id === settings.space) || null;
async function loadSpaces() {
  try { spacesList = (await getJSON("/api/spaces")).spaces; } catch { spacesList = []; }
  if (settings.space && !activeSpace()) { settings.space = null; saveSettings(); }
  renderSpaces();
}
function renderSpaces() {
  const sp = activeSpace();
  $("spaces").hidden = !!sp;
  $("spActive").hidden = !sp;
  if (sp) $("spName").textContent = sp.name;
  $("spList").innerHTML = spacesList.map((x) => `<button data-sp="${x.id}" title="${esc(x.instructions || x.name)}"><span class="ini">${esc((x.name[0] || "?").toUpperCase())}</span><span class="n">${esc(x.name)}</span><span class="c">${x.conversations || ""}</span></button>`).join("");
  $("spList").querySelectorAll("[data-sp]").forEach((b) => { b.onclick = () => enterSpace(+b.dataset.sp); });
  renderConversations(conversations);
}
function enterSpace(id) {
  settings.space = id; saveSettings(); renderSpaces();
  const c = currentConv();
  if (!c || c.space_id !== id) newConversation();
}
$("spBack").onclick = () => { settings.space = null; saveSettings(); renderSpaces(); };
$("spNew").onclick = () => openSpaceDlg(null);
$("spEdit").onclick = () => openSpaceDlg(activeSpace());
function openSpaceDlg(sp) {
  spEditing = sp;
  $("spDlgTitle").textContent = sp ? "Modifier l'espace" : "Nouvel espace";
  $("spDlgName").value = sp?.name || ""; $("spDlgInstr").value = sp?.instructions || "";
  $("spDlgDel").hidden = !sp;
  const cols = (library?.collections || []);
  $("spDlgCols").innerHTML = cols.length ? cols.map((c) => `<label><input type="checkbox" value="${c.id}" ${sp?.collections.includes(c.id) ? "checked" : ""}>${esc(c.name)}${c.kind === "code" ? " · code" : ""}</label>`).join("")
    : '<p class="note">Aucune collection : ajoute des documents dans la Bibliothèque.</p>';
  $("spaceDlg").classList.add("open"); $("spDlgName").focus();
}
$("spDlgCancel").onclick = () => $("spaceDlg").classList.remove("open");
$("spaceDlg").addEventListener("click", (e) => { if (e.target.id === "spaceDlg") $("spaceDlg").classList.remove("open"); });
$("spDlgOk").onclick = async () => {
  const name = $("spDlgName").value.trim();
  if (!name) { $("spDlgName").focus(); return; }
  const body = { name, instructions: $("spDlgInstr").value, collections: [...$("spDlgCols").querySelectorAll("input:checked")].map((i) => +i.value) };
  try {
    const sp = await (await send_(spEditing ? `/api/spaces/${spEditing.id}` : "/api/spaces", spEditing ? "PATCH" : "POST", body)).json();
    $("spaceDlg").classList.remove("open");
    await loadSpaces();
    if (!spEditing) enterSpace(sp.id);
    toast(spEditing ? "Espace mis à jour." : `Espace <b>${esc(sp.name)}</b> créé.`);
  } catch (e) { toast(esc(e.message)); }
};
$("spDlgDel").onclick = async () => {
  if (!spEditing || !confirm(`Supprimer l'espace « ${spEditing.name} » ? Ses conversations sont conservées.`)) return;
  await send_(`/api/spaces/${spEditing.id}`, "DELETE");
  $("spaceDlg").classList.remove("open");
  if (settings.space === spEditing.id) settings.space = null;
  saveSettings(); await loadSpaces(); loadConversations();
};
async function moveToSpace(spaceId) {
  const c = currentConv(); if (!c) { toast("Ouvre d'abord une conversation."); return; }
  await send_(`/api/conversations/${c.id}/space`, "PUT", { space_id: spaceId });
  await loadConversations(); await loadSpaces();
  toast(spaceId ? `Conversation rangée dans <b>${esc(spacesList.find((x) => x.id === spaceId)?.name || "")}</b>.` : "Conversation retirée de l'espace.");
}

/* ============================================================
   RECHERCHE APPROFONDIE et ANALYSE DE DONNÉES — même déroulé :
   étapes en direct, puis réponse finale, enregistrée dans la conversation
   ============================================================ */
let deepNext = false, sbGlobal = null, palCanvases = [];
setInterval(() => getJSON("/api/canvas").then((d) => { palCanvases = d.canvases.slice(0, 12); }).catch(() => {}), 60000);
getJSON("/api/canvas").then((d) => { palCanvases = d.canvases.slice(0, 12); }).catch(() => {});
getJSON("/api/sandbox").then((d) => { sbGlobal = d; }).catch(() => {});
function renderDeepBtn() {
  const b = $("deepBtn"); if (!b) return;
  b.style.display = searchAvailable ? "" : "none";
  b.classList.toggle("on", deepNext);
  b.title = deepNext ? "Recherche approfondie activée pour le prochain message (clic pour annuler)" : "Recherche approfondie : plusieurs recherches, lecture de nombreuses pages, rapport sourcé";
}
$("deepBtn").onclick = () => { deepNext = !deepNext; if (deepNext) { webForce = false; renderWebBtn(); } renderDeepBtn(); input.focus(); };
setInterval(renderDeepBtn, 3000); renderDeepBtn();
function analysisEl(a) {
  const d = document.createElement("div");
  d.innerHTML = (a.images?.length ? `<div class="an-imgs">${a.images.map((f) => `<img src="/api/analysis/${encodeURIComponent(f)}" alt="Graphique" loading="lazy">`).join("")}</div>` : "")
    + `<details class="an-code"><summary>Script Python${a.ok ? "" : " (en échec)"} · ${esc(a.file || "")}</summary><pre><code>${highlightLang(a.code || "", "py")}</code></pre>${a.output ? `<pre>${esc(a.output)}</pre>` : ""}</details>`;
  d.querySelectorAll("img").forEach((im) => { im.onclick = () => window.open(im.src, "_blank"); });
  return d;
}
async function sendSpecial(kind, text, body, fileName) {
  exitHero(); $("empty")?.remove();
  deepNext = false; renderDeepBtn();
  setBusy(true);
  const userMsg = { role: "user", content: text || (fileName ? `Analyse ${fileName}` : ""), meta: fileName ? { attachments: [{ name: fileName, text: "" }] } : undefined };
  history.push(userMsg); chat.appendChild(msgEl(userMsg, history.length - 1));
  setEmotion(kind === "research" ? "curious" : "focus"); setEntityState(kind === "research" ? "recherche approfondie…" : "analyse…");
  const el = document.createElement("div"); el.className = "msg atom";
  el.innerHTML = `<details class="rs-live" open><summary>${kind === "research" ? "Recherche approfondie en cours…" : "Analyse en cours…"}</summary><div class="lv"></div></details><div class="body md"></div>`;
  chat.appendChild(el); scroller.scrollTop = scroller.scrollHeight;
  const lv = el.querySelector(".lv"), out = el.querySelector(".body"), sum = el.querySelector("summary");
  let final = "", q = false;
  controller = new AbortController();
  if (kind === "research") { entity.feeding = true; entity.feedColor = [110, 170, 255]; } else entity.scan = true;
  try {
    const r = await api(`/api/${kind}`, { method: "POST", signal: controller.signal, body: JSON.stringify({ ...body, conversation_id: settings.conversationId }) });
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true }); let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === "meta") { if (settings.conversationId !== ev.conversation_id) { settings.conversationId = ev.conversation_id; saveSettings(); loadConversations(); } }
        else if (ev.type === "progress") { const d = document.createElement("div"); d.className = "st"; d.textContent = ev.text; lv.appendChild(d); sum.textContent = ev.text; entity.tokenKick = 1; scroller.scrollTop = scroller.scrollHeight; }
        else if (ev.type === "token") {
          if (!final) { el.querySelector(".rs-live").open = false; setEmotion("talking"); entity.feeding = false; }
          final += ev.text; entity.tokenKick = 1;
          if (!q) { q = true; requestAnimationFrame(() => { q = false; out.innerHTML = md(final.replace(/^\s*\[[a-z_]+\]\s*/i, "")); scroller.scrollTop = scroller.scrollHeight; }); }
        } else if (ev.type === "error") throw new Error(ev.message);
      }
    }
    setBusy(false);
    await openConversation(settings.conversationId);
    setEmotion("joy");
  } catch (err) {
    setBusy(false); entity.glitch = 1;
    if (err.name === "AbortError") { toast("Arrêté."); await openConversation(settings.conversationId); }
    else { el.replaceWith(msgEl({ role: "assistant", content: err.message, error: true }, -1)); setEmotion("fear"); }
  } finally {
    controller = null; entity.feeding = false; entity.scan = false; setBusy(false); scheduleRest(); loadConversations();
  }
}

/* ============================================================
   CANEVAS — un document modifié à deux, avec ses versions
   ============================================================ */
let cvs = null, cvsTimer = 0, cvsPreview = false;
const CVS_QUICK = [["Corriger", "Corrige l'orthographe, la grammaire et la ponctuation, sans changer le style."], ["Raccourcir", "Raccourcis d'environ un tiers en gardant l'essentiel."],
  ["Développer", "Développe avec plus de détails et d'exemples concrets."], ["Plus formel", "Rends le ton plus formel et professionnel."], ["Plus simple", "Simplifie : phrases courtes, mots simples."],
  ["En anglais", "Traduis en anglais."], ["Structurer", "Structure avec des titres, des listes et des paragraphes courts."]];
$("cvsQuick").innerHTML = CVS_QUICK.map(([t], i) => `<button data-q="${i}">${t}</button>`).join("");
$("cvsQuick").querySelectorAll("button").forEach((b) => { b.onclick = () => canvasAsk(CVS_QUICK[+b.dataset.q][1]); });
function cvsRender() {
  $("canvasPane").classList.toggle("code", cvs.kind === "code");
  $("cvsTitle").value = cvs.title; $("cvsText").value = cvs.content;
  $("cvsVersions").innerHTML = cvs.versions.map((v) => `<option value="${v.i}" ${v.i === cvs.versions.length - 1 ? "selected" : ""}>v${v.i + 1} · ${esc(v.by)} · ${new Date(v.at * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}${v.note ? " · " + esc(v.note.slice(0, 30)) : ""}</option>`).reverse().join("");
  cvsShowView();
}
function cvsShowView() {
  $("cvsText").hidden = cvsPreview; $("cvsView").hidden = !cvsPreview;
  if (cvsPreview) cvs.kind === "code" ? ($("cvsView").innerHTML = `<pre><code>${esc($("cvsText").value)}</code></pre>`) : setMd($("cvsView"), $("cvsText").value);
}
async function openCanvas(id) {
  try { cvs = await getJSON(`/api/canvas/${id}`); } catch (e) { toast(esc(e.message)); return; }
  cvsPreview = false; $("canvasPane").hidden = false; cvsRender(); $("cvsText").focus();
}
async function newCanvas(title, content, kind = "doc") {
  const c = await (await send_("/api/canvas", "POST", { title, content, kind, conversation_id: settings.conversationId })).json();
  openCanvas(c.id);
}
function canvasFromMessage(m) {
  let text = (m.content || "").replace(/^\s*\[[a-z_]+\]\s*/i, "").trim(), kind = "doc";
  const code = text.match(/^```[\w+#.-]*\n([\s\S]*?)\n?```$/);
  if (code) { text = code[1]; kind = "code"; }
  const title = (text.match(/^#+\s*(.+)$/m)?.[1] || currentConv()?.title || "Document").slice(0, 80);
  newCanvas(title, text, kind);
}
function cvsSave() {
  clearTimeout(cvsTimer);
  cvsTimer = setTimeout(async () => {
    if (!cvs) return;
    try { cvs = await (await send_(`/api/canvas/${cvs.id}`, "PUT", { content: $("cvsText").value, title: $("cvsTitle").value })).json(); cvsRenderVersions(); } catch {}
  }, 1200);
}
function cvsRenderVersions() { const keepText = $("cvsText").value; const t = $("cvsTitle").value; cvsRender(); $("cvsText").value = keepText; $("cvsTitle").value = t; }
$("cvsText").addEventListener("input", cvsSave);
$("cvsTitle").addEventListener("input", cvsSave);
const cvsSelection = () => { const t = $("cvsText"); return t.selectionEnd > t.selectionStart ? t.value.slice(t.selectionStart, t.selectionEnd) : ""; };
["select", "keyup", "mouseup"].forEach((ev) => $("cvsText").addEventListener(ev, () => { const s = cvsSelection(); $("cvsSel").textContent = s ? `${s.length} car. sélectionnés` : ""; }));
async function canvasAsk(instruction) {
  instruction = (instruction || $("cvsInstr").value).trim(); if (!cvs || instruction.length < 2) { $("cvsInstr").focus(); return; }
  const selection = cvsSelection();
  clearTimeout(cvsTimer);
  $("canvasPane").classList.add("busy"); $("cvsGo").disabled = true; $("cvsGo").innerHTML = '<span class="spin"></span>'; setEmotion("focus");
  try {
    await send_(`/api/canvas/${cvs.id}`, "PUT", { content: $("cvsText").value, title: $("cvsTitle").value });
    cvs = await (await send_(`/api/canvas/${cvs.id}/edit`, "POST", { instruction, selection })).json();
    cvsRender(); $("cvsInstr").value = ""; entity.absorb = 1; toast(selection ? "Passage modifié par Atom." : "Document modifié par Atom · version précédente dans le menu des versions.");
  } catch (e) { toast(`<b>Canevas</b> · ${esc(e.message)}`); }
  finally { $("canvasPane").classList.remove("busy"); $("cvsGo").disabled = false; $("cvsGo").textContent = "Modifier"; setEmotion("idle"); }
}
$("cvsGo").onclick = () => canvasAsk();
$("cvsInstr").addEventListener("keydown", (e) => { if (e.key === "Enter") canvasAsk(); });
$("cvsVersions").onchange = async (e) => {
  const i = +e.target.value; if (i === cvs.versions.length - 1) return;
  if (!confirm(`Revenir à la version ${i + 1} ? (la version actuelle reste dans l'historique)`)) { cvsRender(); return; }
  const { content } = await getJSON(`/api/canvas/${cvs.id}/versions/${i}`);
  cvs = await (await send_(`/api/canvas/${cvs.id}`, "PUT", { content })).json(); cvsRender();
};
$("cvsPreview").onclick = () => { cvsPreview = !cvsPreview; cvsShowView(); };
$("cvsCopy").onclick = (e) => flashCopy(e.currentTarget, $("cvsText").value);
$("cvsDownload").onclick = () => {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([$("cvsText").value], { type: "text/plain" }));
  a.download = ($("cvsTitle").value || "document").replace(/[^\w\- ]+/g, "").trim() + (cvs?.kind === "code" ? ".txt" : ".md"); a.click();
};
$("cvsClose").onclick = () => { clearTimeout(cvsTimer); if (cvs) send_(`/api/canvas/${cvs.id}`, "PUT", { content: $("cvsText").value, title: $("cvsTitle").value }).catch(() => {}); $("canvasPane").hidden = true; cvs = null; };

/* ============================================================
   SERVEUR PROXMOX — lecture seule
   ============================================================ */
let pxTimer = 0;
const pxGb = (b) => (b / 1e9).toFixed(b > 1e11 ? 0 : 1).replace(".", ",") + " Go";
const pxDur = (s) => { const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600); return d ? `${d} j ${h} h` : `${h} h ${Math.floor((s % 3600) / 60)} min`; };
const pxBar = (pct, warn) => `<div class="bar"><i style="width:${Math.min(100, pct)}%${pct >= warn ? ";background:var(--danger,#e66)" : ""}"></i></div>`;
async function loadProxmox() {
  let d; try { d = await getJSON("/api/proxmox"); } catch (e) { return; }
  $("pxSetup").hidden = d.configured; $("pxBody").hidden = !d.configured;
  clearTimeout(pxTimer);
  if (!d.configured) return;
  const s = d.settings;
  $("pxUpd").textContent = d.ok ? `relevé à ${new Date(d.updated * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
  $("pxAlerts").innerHTML = !d.ok ? `<p class="note" style="color:var(--danger,#e66)">Proxmox injoignable : ${esc(d.error)}</p>`
    : d.alerts.map((a) => `<p class="note" style="color:var(--danger,#e66)">⚠ ${esc(a.title)} — ${esc(a.body)}</p>`).join("");
  $("pxNodes").innerHTML = d.nodes.map((n) => `<div class="px-node"><div class="row" style="justify-content:space-between"><b>${esc(n.name)}</b><span class="note">${n.status === "online" ? `en marche depuis ${pxDur(n.uptime)}` : esc(n.status)}</span></div>
    ${n.model ? `<p class="note" style="margin:2px 0 6px">${esc(n.model)} · ${n.cores} cœurs${n.load ? ` · charge ${n.load.map(esc).join(" / ")}` : ""}</p>` : ""}
    <div class="metric"><div class="l"><span>Processeur</span><span>${n.cpu.toFixed(0)} %</span></div>${pxBar(n.cpu, s.cpu)}</div>
    <div class="metric"><div class="l"><span>Mémoire</span><span>${pxGb(n.mem_used)} / ${pxGb(n.mem_total)}</span></div>${pxBar(n.mem, s.mem)}</div>
    <div class="metric"><div class="l"><span>Disque système</span><span>${n.disk.toFixed(0)} %</span></div>${pxBar(n.disk, s.storage)}</div></div>`).join("");
  $("pxGuests").innerHTML = d.guests.map((g) => `<div class="px-g ${g.status === "running" ? "" : "off"}"><span class="st-dot ${g.status === "running" ? "ok" : "off"}"></span>
    <span class="n"><b>${esc(g.name)}</b> <small>${g.type} ${g.id}${d.nodes.length > 1 ? " · " + esc(g.node) : ""}</small></span>
    ${g.status === "running" ? `<span class="v">${g.cpu.toFixed(0)} %</span><span class="v">${pxGb(g.mem_used)}</span><span class="v t">${pxDur(g.uptime)}</span>` : `<span class="v t">${esc(g.status)}</span>`}</div>`).join("") || '<p class="note">Aucune VM ni conteneur.</p>';
  $("pxStorages").innerHTML = d.storages.map((st) => `<div class="metric"><div class="l"><span>${esc(st.name)} <small class="note">${esc(st.node)} · ${esc(st.kind || "")}</small></span><span>${pxGb(st.used)} / ${pxGb(st.total)}</span></div>${pxBar(st.pct, s.storage)}</div>`).join("");
  $("pxNotify").checked = s.notify; $("pxGuestDown").checked = s.guest_down;
  $("pxCpu").value = s.cpu; $("pxMem").value = s.mem; $("pxMin").value = s.minutes; $("pxSto").value = s.storage;
  if ($("settings").classList.contains("open")) pxTimer = setTimeout(loadProxmox, 30000);
}
const pxSave = (patch) => send_("/api/proxmox", "PUT", patch).then(() => toast("Réglages d'alerte enregistrés.")).catch((e) => toast(esc(e.message)));
$("pxRefresh").onclick = loadProxmox;
$("pxNotify").onchange = () => pxSave({ notify: $("pxNotify").checked });
$("pxGuestDown").onchange = () => pxSave({ guest_down: $("pxGuestDown").checked });
[["pxCpu", "cpu"], ["pxMem", "mem"], ["pxMin", "minutes"], ["pxSto", "storage"]].forEach(([id, k]) => { $(id).onchange = () => pxSave({ [k]: +$(id).value }); });
