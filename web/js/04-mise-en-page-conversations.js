"use strict";

/* ============================================================
   MISE EN PAGE (barre latérale, panneau)
   ============================================================ */
const app = $("app");
const narrow = () => matchMedia("(max-width: 760px)").matches;
const medium = () => matchMedia("(max-width: 1180px)").matches;

// En mode Code, le panneau de l'entité est replié par défaut (réglage séparé) pour laisser la place au code.
const panelKey = () => (app.dataset.view === "code" ? "panelCode" : "panel");
function applyLayout() {
  const on = app.dataset.view === "code" ? !!settings.panelCode : settings.panel;
  app.classList.toggle("no-side", !settings.side);
  app.classList.toggle("no-panel", !on);
  $("sideOpen").style.display = (!settings.side || narrow()) ? "" : "none";
  $("panelBtn").classList.toggle("on", medium() ? app.classList.contains("panel-open") : on);
}
$("sideClose").onclick = () => { if (narrow()) app.classList.remove("side-open"); else { settings.side = false; saveSettings(); applyLayout(); } };
$("sideOpen").onclick = () => { if (narrow()) app.classList.add("side-open"); else { settings.side = true; saveSettings(); applyLayout(); } };
$("panelBtn").onclick = () => {
  if (medium()) app.classList.toggle("panel-open");
  else { settings[panelKey()] = !(app.dataset.view === "code" ? settings.panelCode : settings.panel); saveSettings(); }
  applyLayout();
  refreshPanel();
  refreshSystem();
};
$("panelClose").onclick = () => { if (medium()) app.classList.remove("panel-open"); else { settings[panelKey()] = false; saveSettings(); } applyLayout(); };
$("scrim").onclick = () => { app.classList.remove("side-open", "panel-open"); applyLayout(); };
addEventListener("resize", applyLayout);
const panelVisible = () => medium() ? app.classList.contains("panel-open") : (app.dataset.view === "code" ? !!settings.panelCode : settings.panel);

/* ============================================================
   CONVERSATIONS
   ============================================================ */
let history = [];
let conversations = [];

function groupOf(ts) {
  const d = new Date(ts * 1000), now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = (day(now) - day(d)) / 86400000;
  if (diff < 1) return "Aujourd'hui";
  if (diff < 2) return "Hier";
  if (diff < 7) return "7 derniers jours";
  if (diff < 30) return "30 derniers jours";
  return "Plus ancien";
}

async function loadConversations() {
  try { conversations = (await getJSON("/api/conversations")).conversations; } catch (e) { console.warn(e); }
  if (!$("search").value.trim()) renderConversations(conversations);
  updateTitle();
}

function convItem(c, snippet) {
  const el = document.createElement("div");
  el.className = "conv" + (c.id === settings.conversationId ? " active" : "");
  const t = document.createElement("div");
  t.className = "t"; t.title = c.title;
  t.textContent = c.title;
  if (c.space_id && !(typeof activeSpace === "function" && activeSpace())) {
    const sp = (typeof spacesList !== "undefined" ? spacesList : []).find((x) => x.id === c.space_id);
    if (sp) { const g = document.createElement("span"); g.className = "sp-tag"; g.textContent = sp.name; t.appendChild(g); }
  }
  if (snippet) { const s = document.createElement("span"); s.className = "snip"; s.textContent = snippet; t.appendChild(s); }
  t.onclick = () => { openConversation(c.id); app.classList.remove("side-open"); };
  t.ondblclick = () => renameInline(el, c);
  const pin = document.createElement("button");
  pin.className = "iconbtn a"; pin.title = c.pinned ? "Désépingler" : "Épingler"; pin.innerHTML = icon("pin");
  if (c.pinned) pin.style.color = "var(--text)";
  pin.onclick = async (e) => { e.stopPropagation(); await send_(`/api/conversations/${c.id}`, "PATCH", { pinned: !c.pinned }); loadConversations(); };
  const del = document.createElement("button");
  del.className = "iconbtn a"; del.title = "Supprimer"; del.innerHTML = icon("trash");
  del.onclick = async (e) => {
    e.stopPropagation();
    if (!confirm(`Supprimer « ${c.title} » ?`)) return;
    await send_(`/api/conversations/${c.id}`, "DELETE");
    if (c.id === settings.conversationId) newConversation();
    loadConversations();
  };
  el.append(t, pin, del);
  return el;
}

let convAnimated = false;
function renderConversations(list, search = false) {
  const sp = typeof activeSpace === "function" ? activeSpace() : null;
  if (sp && !search) list = list.filter((c) => c.space_id === sp.id);
  const nav = $("convList");
  nav.innerHTML = "";
  const animate = !convAnimated || search; convAnimated = true;
  let k = 0;
  const _append = nav.appendChild.bind(nav);
  nav.appendChild = (el) => { if (animate && el.classList?.contains("conv")) { el.classList.add("in"); el.style.setProperty("--i", k++); } return _append(el); };
  if (!list.length) {
    nav.innerHTML = `<div class="side-empty">${search ? "Aucun résultat." : sp ? "Aucune conversation dans cet espace : écris un message pour commencer." : "Aucune conversation pour l'instant."}</div>`;
    return;
  }
  if (search) {
    for (const c of list) nav.appendChild(convItem(c, c.snippet ? c.snippet.slice(0, 80) : ""));
    return;
  }
  const pinned = list.filter((c) => c.pinned);
  const groups = new Map();
  if (pinned.length) groups.set("Épinglées", pinned);
  for (const c of list.filter((c) => !c.pinned)) {
    const g = groupOf(c.updated_at);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(c);
  }
  for (const [name, items] of groups) {
    const h = document.createElement("div"); h.className = "group"; h.textContent = name;
    nav.appendChild(h);
    for (const c of items) nav.appendChild(convItem(c));
  }
}

function renameInline(el, c) {
  const inp = document.createElement("input");
  inp.value = c.title;
  el.innerHTML = ""; el.appendChild(inp); inp.focus(); inp.select();
  const done = async (save) => {
    const v = inp.value.trim();
    if (save && v && v !== c.title) await send_(`/api/conversations/${c.id}`, "PATCH", { title: v });
    loadConversations();
  };
  inp.onkeydown = (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); };
  inp.onblur = () => done(true);
}

let searchTimer = 0;
$("palKbd").onclick = (e) => { e.preventDefault(); openPalette(); };
$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = $("search").value.trim();
  if (q.length < 2) { renderConversations(conversations); return; }
  searchTimer = setTimeout(async () => {
    try { renderConversations((await getJSON("/api/search?q=" + encodeURIComponent(q))).results, true); } catch {}
  }, 200);
});

function currentConv() { return conversations.find((c) => c.id === settings.conversationId); }
function updateTitle() {
  if (typeof currentView !== "undefined" && currentView !== "chat") { $("title").textContent = currentView === "code" ? "Code" : "Bibliothèque"; return; }
  const c = currentConv();
  $("title").textContent = c ? c.title : "Nouvelle conversation";
  $("pinBtn").style.display = c ? "" : "none";
  $("exportBtn").style.display = c ? "" : "none";
  $("pinBtn").classList.toggle("on", !!(c && c.pinned));
  $("pinBtn").title = c && c.pinned ? "Désépingler" : "Épingler";
  document.title = c ? `${c.title} · Atom` : "Atom";
}
$("title").onclick = () => {
  const c = currentConv();
  if (!c) return;
  const inp = document.createElement("input");
  inp.className = "title-input"; inp.value = c.title;
  $("title").replaceWith(inp); inp.focus(); inp.select();
  const done = async (save) => {
    const v = inp.value.trim();
    inp.replaceWith(titleBtn);
    if (save && v && v !== c.title) await send_(`/api/conversations/${c.id}`, "PATCH", { title: v });
    loadConversations();
  };
  inp.onkeydown = (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); };
  inp.onblur = () => done(true);
};
const titleBtn = $("title");
$("pinBtn").onclick = async () => {
  const c = currentConv(); if (!c) return;
  await send_(`/api/conversations/${c.id}`, "PATCH", { pinned: !c.pinned });
  loadConversations();
};
$("exportBtn").onclick = () => {
  const c = currentConv(); if (!c) return;
  let out = `# ${c.title}\n\n`;
  for (const m of history) {
    const who = m.role === "user" ? "**Moi**" : "**Atom**";
    const when = m.created_at ? ` · ${new Date(m.created_at * 1000).toLocaleString("fr-FR")}` : "";
    out += `${who}${when}\n\n${m.content}\n\n---\n\n`;
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([out], { type: "text/markdown" }));
  a.download = (c.title.replace(/[\\/:*?"<>|]+/g, "").slice(0, 60) || "conversation") + ".md";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};

async function openConversation(id) {
  if (busy) return;
  if (currentView !== "chat") showView("chat");
  try {
    history = (await getJSON(`/api/conversations/${id}/messages`)).messages;
    settings.conversationId = id;
  } catch { history = []; settings.conversationId = null; }
  saveSettings();
  restoreDraft();
  const c = conversations.find((x) => x.id === id);
  if (c?.model && [...modelSel.options].some((o) => o.value === c.model)) modelSel.value = c.model;
  else modelSel.value = settings.model;
  renderHistory();
  renderConversations(conversations);
  updateTitle();
  input.focus();
}

function newConversation() {
  if (busy) return;
  if (currentView !== "chat") showView("chat");
  settings.conversationId = null;
  saveSettings();
  history = [];
  restoreDraft();
  modelSel.value = settings.model;
  renderHistory();
  renderConversations(conversations);
  updateTitle();
  setEmotion("idle");
  app.classList.remove("side-open");
  input.focus();
}
$("newConv").onclick = newConversation;
