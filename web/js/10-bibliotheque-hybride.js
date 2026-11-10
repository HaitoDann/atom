"use strict";

/* ============================================================
   BIBLIOTHÈQUE — documents et projets de code
   ============================================================ */
let library = { collections: [], server_projects: [] }, libSel = null, libTimer = 0;
let scope = store.get("scope", "auto");   // "auto" | "none" | "3,5"

let currentView = "chat";
function showView(v) {
  currentView = v; store.set("view", v); app.dataset.view = v; applyLayout();
  $("libView").hidden = v !== "library";
  $("codeView").hidden = v !== "code";
  $("dashView").hidden = v !== "dash";
  $("agendaView").hidden = v !== "agenda";
  $("scroller").hidden = v !== "chat";
  document.querySelector(".composer").hidden = v !== "chat";
  $("navLib").classList.toggle("on", v === "library");
  $("navCode").classList.toggle("on", v === "code");
  $("navDash").classList.toggle("on", v === "dash");
  $("navAgenda").classList.toggle("on", v === "agenda");
  ["pinBtn", "exportBtn"].forEach((id) => { if (v !== "chat") $(id).style.display = "none"; });
  app.classList.remove("side-open");
  if (v !== "chat") exitHero();
  else if (!history.length) requestAnimationFrame(() => enterHero());
  if (v === "library") { $("title").textContent = "Bibliothèque"; loadLibrary(); }
  else if (v === "code") { $("title").textContent = "Code"; loadCodeProjects(); }
  else if (v === "dash") { $("title").textContent = "Tableau de bord"; loadDashboard(); }
  else if (v === "agenda") { $("title").textContent = "Agenda"; loadAgendaView(); }
  else { updateTitle(); if (!library.collections.some((c) => c.status === "indexing")) clearTimeout(libTimer); }
  if (typeof syncTabbar === "function") syncTabbar();
}
$("navLib").onclick = () => showView(currentView === "library" ? "chat" : "library");
$("navCode").onclick = () => showView(currentView === "code" ? "chat" : "code");
$("navDash").onclick = () => showView(currentView === "dash" ? "chat" : "dash");

async function loadLibrary() {
  try { library = await getJSON("/api/library"); } catch { return; }
  if (!libSel || !library.collections.some((c) => c.id === libSel)) libSel = library.collections[0]?.id ?? null;
  const hadCols = !!library.collections.length;
  renderLibrary();
  renderScope();
  if (hadCols && !document.querySelector("#empty .card[data-cap]")) renderCards();
  const busyIdx = library.collections.some((c) => c.status === "indexing");
  entity.feedColor = busyIdx ? [235, 235, 240] : [110, 170, 255];
  if (!$("libView").hidden || !$("codeView").hidden) entity.feeding = busyIdx;
  watchIndexing();
  clearTimeout(libTimer);
  // Pendant une indexation, on suit la progression quelle que soit la vue (et on prévient à la fin).
  if (busyIdx || !$("libView").hidden) libTimer = setTimeout(loadLibrary, busyIdx ? 2000 : 15000);
}

// ---- suivi des indexations : progression lisible + notification de fin
const idxSeen = new Map();   // id → { status, phase, done, t }
function idxText(c) {
  const p = c.progress;
  if (c.status !== "indexing") return c.message || "";
  if (!p) return c.message || "Indexation…";
  if (p.phase === "clone") return "Téléchargement du dépôt…";
  if (p.phase === "read") return `Lecture de ${p.total} fichiers…`;
  if (p.phase === "embed") {
    if (!p.total) return "Finalisation…";
    const pct = Math.floor((100 * p.done) / p.total);
    const s = idxSeen.get(c.id), rate = s?.rate;
    const left = rate > 0 ? Math.max(1, Math.round((p.total - p.done) / rate)) : 0;
    return `Indexation : ${p.done} / ${p.total} passages · ${pct} %` + (left ? ` · ~${left < 90 ? left + " s" : Math.round(left / 60) + " min"}` : "");
  }
  return c.message || "Indexation…";
}
function idxPct(c) {
  const p = c.progress;
  if (c.status !== "indexing" || !p) return null;
  return p.phase === "embed" && p.total ? p.done / p.total : p.phase === "read" ? 0.02 : 0;
}
function watchIndexing() {
  const now = performance.now() / 1000;
  for (const c of library.collections) {
    const prev = idxSeen.get(c.id), p = c.progress || {};
    const cur = { status: c.status, phase: p.phase, done: p.done || 0, t: now, rate: prev?.rate || 0 };
    if (prev && prev.phase === "embed" && p.phase === "embed" && cur.done > prev.done) {
      const r = (cur.done - prev.done) / Math.max(0.5, now - prev.t);
      cur.rate = prev.rate ? prev.rate * 0.6 + r * 0.4 : r;
    }
    if (prev && prev.status === "indexing" && c.status !== "indexing") {
      if (c.status === "ready") toast(`<b>${esc(c.name)}</b> · prêt : ${c.documents} fichiers, ${c.chunks} passages indexés.`);
      else if (c.status === "error") toast(`<b>${esc(c.name)}</b> · ${esc(c.message || "indexation impossible")}`);
    }
    // le projet ouvert dans la vue Code : la liste des fichiers arrive dès la fin de la lecture
    if (!$("codeView").hidden && c.id === code.project && prev
        && (prev.status !== c.status || (prev.phase !== p.phase && p.phase === "embed"))) loadCodeFiles();
    else if (!$("codeView").hidden && c.id === code.project) renderCodeInfo(c);
    idxSeen.set(c.id, cur);
  }
}
// lancée depuis l'interface : la fin sera signalée même si elle survient avant le premier relevé
function markIndexing(id) { idxSeen.set(id, { status: "indexing", phase: "clone", done: 0, t: performance.now() / 1000, rate: 0 }); }
function renderCodeInfo(c) {
  const pct = idxPct(c);
  $("cvInfo").innerHTML = c.status === "indexing"
    ? `${esc(idxText(c))}<span class="idxbar"><i style="width:${Math.round((pct || 0) * 100)}%"></i></span>`
    : esc(c.status === "error" ? c.message || "Erreur" : `${code.files.length} fichiers · ${c.source || ""}`);
}

function renderLibrary() {
  const list = $("libCols");
  list.innerHTML = "";
  for (const c of library.collections) {
    const b = document.createElement("button");
    b.className = "lib-col" + (c.id === libSel ? " on" : "");
    const st = c.status === "indexing" ? '<span class="spin"></span>' : c.status === "error" ? '<span class="err">!</span>' : "";
    b.innerHTML = `${icon(c.kind === "code" ? "code" : "folder")}<span class="n">${esc(c.name)}</span>${st}<span class="c">${c.documents}</span>`;
    b.onclick = () => { libSel = c.id; renderLibrary(); };
    list.appendChild(b);
  }
  renderCollection();
}

async function renderCollection() {
  const box = $("libMain");
  const c = library.collections.find((x) => x.id === libSel);
  if (!c) { box.innerHTML = '<div class="side-empty">Aucune collection.</div>'; return; }
  let d;
  try { d = await getJSON(`/api/library/collections/${c.id}/documents`); } catch { return; }
  const isCode = c.kind === "code";
  box.innerHTML = `
    <div class="lib-head">
      <div><h2>${esc(c.name)}</h2>
        <p>${isCode ? `Projet de code · ${esc(c.source || "")}` : "Documents"} · ${d.documents.length} fichier${d.documents.length > 1 ? "s" : ""} · ${c.chunks} passage${c.chunks > 1 ? "s" : ""} indexé${c.chunks > 1 ? "s" : ""}</p>
        ${c.message || c.status === "indexing" ? `<p class="${c.status === "error" ? "lib-err" : ""}">${esc(idxText(c))}${c.status === "indexing" ? `<span class="idxbar"><i style="width:${Math.round((idxPct(c) || 0) * 100)}%"></i></span>` : ""}</p>` : ""}
      </div>
      <div class="row">
        ${isCode ? `<button class="btn" data-a="sync">${icon("refresh")} Mettre à jour</button>` : ""}
        <button class="btn" data-a="ask">${icon("spark")} Poser une question</button>
        <button class="iconbtn" data-a="rename" title="Renommer">${icon("edit")}</button>
        <button class="iconbtn" data-a="del" title="Supprimer la collection">${icon("trash")}</button>
      </div>
    </div>
    ${isCode ? "" : `<label class="drop-zone" id="libDrop">${icon("download")}<b>Dépose tes documents ici</b><span>ou clique pour choisir · PDF, Word, texte, Markdown, HTML, CSV…</span><input type="file" multiple hidden id="libFile"></label>`}
    <table class="lib-table"><thead><tr><th>${isCode ? "Fichier" : "Document"}</th><th>${isCode ? "Taille" : "Pages"}</th><th>Passages</th><th></th></tr></thead><tbody></tbody></table>`;
  const tb = box.querySelector("tbody");
  if (!d.documents.length) tb.innerHTML = `<tr><td colspan="4" class="none">${isCode ? "Indexation en cours…" : "Aucun document pour l'instant."}</td></tr>`;
  for (const doc of d.documents.slice(0, 400)) {
    const tr = document.createElement("tr");
    const status = doc.status === "indexing" ? '<span class="spin"></span> lecture…' : doc.status === "error" ? `<span class="lib-err" title="${esc(doc.message || "")}">${esc((doc.message || "erreur").slice(0, 60))}</span>` : doc.chunks;
    tr.innerHTML = `<td class="nm"><div>${icon(isCode ? "code" : "doc")}<span>${esc(isCode ? doc.path : doc.name)}</span></div></td><td>${isCode ? fmtBytes(doc.size) : (doc.pages || "—")}</td><td>${status}</td><td class="act"></td>`;
    const act = tr.querySelector(".act");
    const v = document.createElement("button"); v.className = "iconbtn"; v.title = "Aperçu"; v.innerHTML = icon("search");
    v.onclick = () => previewDoc(doc.id);
    act.appendChild(v);
    if (!isCode) {
      const dl = document.createElement("a"); dl.className = "iconbtn"; dl.title = "Télécharger"; dl.href = `/api/library/documents/${doc.id}/file`; dl.innerHTML = icon("download");
      const del = document.createElement("button"); del.className = "iconbtn"; del.title = "Supprimer"; del.innerHTML = icon("trash");
      del.onclick = async () => { if (!confirm(`Supprimer « ${doc.name} » de la bibliothèque ?`)) return; await send_(`/api/library/documents/${doc.id}`, "DELETE"); loadLibrary(); };
      act.append(dl, del);
    }
    tb.appendChild(tr);
  }
  if (d.documents.length > 400) tb.insertAdjacentHTML("beforeend", `<tr><td colspan="4" class="none">… et ${d.documents.length - 400} autres fichiers</td></tr>`);
  box.querySelector('[data-a="del"]').onclick = async () => {
    if (!confirm(`Supprimer la collection « ${c.name} » et tout son index ?`)) return;
    await send_(`/api/library/collections/${c.id}`, "DELETE"); libSel = null; loadLibrary();
  };
  box.querySelector('[data-a="rename"]').onclick = async () => {
    const n = prompt("Nouveau nom", c.name); if (!n?.trim()) return;
    await send_(`/api/library/collections/${c.id}`, "PATCH", { name: n.trim(), kind: c.kind }); loadLibrary();
  };
  box.querySelector('[data-a="ask"]').onclick = () => { setScope(String(c.id)); showView("chat"); newConversation(); fillInput(isCode ? "Explique-moi l'architecture de ce projet." : "Que contiennent ces documents ? "); };
  box.querySelector('[data-a="sync"]')?.addEventListener("click", async () => { await send_(`/api/library/collections/${c.id}/sync`, "POST"); markIndexing(c.id); toast("Mise à jour du projet lancée."); loadLibrary(); });
  const drop = $("libDrop");
  if (drop) {
    $("libFile").onchange = (e) => { uploadDocs(c.id, [...e.target.files]); e.target.value = ""; };
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("over"));
    drop.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.remove("over"); $("drop").classList.remove("on"); uploadDocs(c.id, [...e.dataTransfer.files]); });
  }
}

async function uploadDocs(cid, files) {
  for (const f of files) {
    if (f.size > 100 * 1024 * 1024) { toast(`<b>${esc(f.name)}</b> · trop gros (100 Mo max)`); continue; }
    try {
      const r = await fetch(`/api/library/collections/${cid}/documents?name=${encodeURIComponent(f.name)}`, { method: "POST", body: f, headers: { "Content-Type": "application/octet-stream", "X-Atom": "1" } });
      if (!r.ok) throw new Error((await r.json()).detail || "échec");
      entity.feedColor = [235, 235, 240]; entity.feeding = true;
      setTimeout(() => { entity.feeding = false; entity.feedColor = [110, 170, 255]; }, 2500);
    } catch (e) { toast(`<b>${esc(f.name)}</b> · ${esc(e.message)}`); }
  }
  toast(`<b>${files.length} document${files.length > 1 ? "s" : ""}</b> ajouté${files.length > 1 ? "s" : ""} · Atom les lit…`);
  loadLibrary();
}

$("libNewDocs").onclick = async () => {
  const n = prompt("Nom de la collection (ex. Administratif, Travail, Homelab)"); if (!n?.trim()) return;
  const c = await (await send_("/api/library/collections", "POST", { name: n.trim(), kind: "docs" })).json();
  libSel = c.id; loadLibrary();
};
$("libNewCode").onclick = () => {
  $("codeDlg").classList.add("open");
  const sel = $("codeServer");
  sel.innerHTML = library.server_projects.length ? library.server_projects.map((p) => `<option>${esc(p)}</option>`).join("") : '<option value="">(aucun dossier dans /projects)</option>';
  $("codeUrl").value = ""; $("codeName").value = "";
  $("codeUrl").focus();
};
$("codeCancel").onclick = () => $("codeDlg").classList.remove("open");
$("codeOk").onclick = async () => {
  const url = $("codeUrl").value.trim(), srv = $("codeServer").value;
  const source = url || srv;
  if (!source) { toast("Indique une adresse GitHub ou choisis un dossier du serveur."); return; }
  const name = $("codeName").value.trim() || source.replace(/\.git$/, "").split("/").filter(Boolean).pop();
  try {
    const c = await (await send_("/api/library/collections", "POST", { name, kind: "code", source })).json();
    $("codeDlg").classList.remove("open"); libSel = c.id; markIndexing(c.id); toast("Projet ajouté · téléchargement puis indexation, je te préviens quand c'est prêt."); loadLibrary();
  } catch (e) { toast(esc(e.message)); }
};

/* Aperçu d'un document : tous ses passages, celui cité mis en évidence */
async function previewDoc(did, chunkId) {
  let d;
  try { d = await getJSON(`/api/library/documents/${did}`); } catch { toast("Document introuvable (supprimé ?)."); return; }
  $("pvTitle").textContent = d.document.path && !d.document.path.startsWith("/") ? d.document.path : d.document.name;
  const body = $("pvBody");
  body.innerHTML = "";
  for (const ch of d.chunks) {
    const el = document.createElement("div");
    el.className = "pv-chunk" + (ch.id === chunkId ? " hit" : "");
    const where = ch.page ? `page ${ch.page}` : ch.line_start ? `lignes ${ch.line_start}-${ch.line_end}` : `passage ${ch.ord + 1}`;
    el.innerHTML = `<small>${where}</small>`;
    const pre = document.createElement(ch.line_start ? "pre" : "div");
    if (ch.line_start) pre.innerHTML = highlight(ch.text.replace(/^# .*\n/, "")); else pre.textContent = ch.text;
    el.appendChild(pre);
    body.appendChild(el);
  }
  if (!d.chunks.length) body.innerHTML = `<p class="note">${esc(d.document.message || "Pas encore indexé.")}</p>`;
  $("preview").classList.add("open");
  requestAnimationFrame(() => body.querySelector(".hit")?.scrollIntoView({ block: "center" }));
}
$("pvClose").onclick = () => $("preview").classList.remove("open");
$("preview").addEventListener("click", (e) => { if (e.target.id === "preview") $("preview").classList.remove("open"); });

/* Portée de la conversation : quelles collections Atom consulte */
function scopeLabel() {
  if (scope === "auto") return "Documents";
  if (scope === "none") return "Sans bibliothèque";
  const ids = scope.split(",").map(Number);
  const names = library.collections.filter((c) => ids.includes(c.id)).map((c) => c.name);
  return names.length ? names.join(", ") : "Documents";
}
function setScope(v) { scope = v; store.set("scope", v); renderScope(); }
function renderScope() {
  $("scopeBtn").innerHTML = icon(scope !== "auto" && scope !== "none" && library.collections.find((c) => String(c.id) === scope)?.kind === "code" ? "code" : "folder") + `<span>${esc(scopeLabel())}</span>`;
  $("scopeBtn").classList.toggle("on", scope !== "auto" && scope !== "none");
}
$("scopeBtn").onclick = (e) => {
  e.stopPropagation();
  const m = $("scopeMenu");
  if (m.classList.toggle("open")) {
    const ids = scope.split(",");
    m.innerHTML = `<button data-v="auto">${icon("folder")}<span><b>Documents</b><small>Atom consulte tes documents quand c'est utile</small></span></button>
      <button data-v="none">${icon("x")}<span><b>Sans bibliothèque</b><small>Ne rien consulter</small></span></button>
      <div class="sep"></div>` + library.collections.map((c) =>
      `<button data-v="${c.id}" class="${ids.includes(String(c.id)) ? "on" : ""}">${icon(c.kind === "code" ? "code" : "folder")}<span><b>${esc(c.name)}</b><small>${c.kind === "code" ? "Projet de code" : "Collection"} · ${c.documents} fichier${c.documents > 1 ? "s" : ""}</small></span></button>`).join("")
      + `<div class="sep"></div><button data-v="manage">${icon("settings")}<span><b>Gérer la bibliothèque…</b></span></button>`;
    m.querySelectorAll("button").forEach((b) => b.onclick = () => {
      m.classList.remove("open");
      if (b.dataset.v === "manage") return showView("library");
      setScope(b.dataset.v);
    });
  }
};
document.addEventListener("click", () => $("scopeMenu").classList.remove("open"));

function docsEl(refs) {
  const d = document.createElement("div");
  d.className = "sources";
  for (const r of refs) {
    const b = document.createElement("button");
    b.className = "src-l";
    b.innerHTML = `<i>D${r.n}</i><span>${esc(r.label)}</span><small>${esc(r.collection)}</small>`;
    b.onclick = () => previewDoc(r.document_id, r.chunk_id);
    d.appendChild(b);
  }
  return d;
}

/* ============================================================
   MODE HYBRIDE (local / auto / Mistral)
   ============================================================ */
let hybridState = null;
let engine = store.get("engine", "default");
const ENGINE_LABEL = () => ({ default: "Par défaut", local: "Local", auto: "Auto", mistral: hybridState?.name || "Mistral" });
function renderEngine() {
  const wrap = $("engineWrap");
  wrap.style.display = hybridState?.configured ? "" : "none";
  if (!hybridState) return;
  const eff = engine === "default" ? hybridState.mode : engine;
  const lbl = engine === "default" ? `${ENGINE_LABEL()[eff]}` : ENGINE_LABEL()[engine];
  $("engineBtn").innerHTML = icon(eff === "local" ? "orb" : "spark") + `<span>${esc(lbl)}</span>`;
  $("engineBtn").classList.toggle("on", eff !== "local");
}
function setEngine(v) { engine = v; store.set("engine", v); renderEngine(); }
$("engineBtn").onclick = (e) => {
  e.stopPropagation();
  const m = $("engineMenu");
  if (!m.classList.toggle("open")) return;
  const n = hybridState?.name || "Mistral";
  const opts = [
    ["default", "orb", `Par défaut (${ENGINE_LABEL()[hybridState.mode]})`, "Le réglage choisi dans Réglages → Hybride"],
    ["local", "orb", "Local", "Tout reste sur ton serveur"],
    ["auto", "spark", "Auto", `${n} pour les demandes complexes, local sinon`],
    ["mistral", "spark", n, `Toujours ${n} (dans les limites de confidentialité)`],
  ];
  m.innerHTML = opts.map(([v, ic, t, d]) => `<button data-v="${v}" class="${engine === v ? "on" : ""}">${icon(ic)}<span><b>${esc(t)}</b><small>${esc(d)}</small></span></button>`).join("")
    + `<div class="sep"></div><button data-v="settings">${icon("settings")}<span><b>Réglages du mode hybride…</b></span></button>`;
  m.querySelectorAll("button").forEach((b) => b.onclick = () => { m.classList.remove("open"); b.dataset.v === "settings" ? openSettings("hybrid") : setEngine(b.dataset.v); });
};
document.addEventListener("click", () => $("engineMenu").classList.remove("open"));

async function loadHybrid() {
  try { hybridState = await getJSON("/api/hybrid"); } catch { return; }
  renderEngine();
  const h = hybridState;
  $("hySetup").style.display = h.configured ? "none" : "";
  $("hySetup").innerHTML = "Aucun fournisseur distant configuré : ajoute une clé (Groq, Cerebras, Gemini…) dans le fichier <code>.env</code> du serveur — <code>ATOM_REMOTE_API_KEY=…</code> ou <code>ATOM_PROVIDERS=…</code> — puis relance Atom. Voir le README.";
  $("hyMode").innerHTML = "";
  for (const [v, t] of [["local", "Local"], ["auto", "Auto"], ["mistral", "Distant"]]) {
    const b = document.createElement("button");
    b.className = "btn" + (h.mode === v ? " primary" : "");
    b.textContent = t; b.disabled = !h.configured && v !== "local";
    b.onclick = () => saveHybrid({ mode: v });
    $("hyMode").appendChild(b);
  }
  $("hyOrch").innerHTML = "";
  for (const [v, t, d] of [["suggest", "Proposer", "Atom répond, puis propose de refaire avec l'orchestration"], ["auto", "Automatique", "Orchestration directe"], ["off", "Jamais", ""]]) {
    const b = document.createElement("button");
    b.className = "btn" + (h.orchestrate === v ? " primary" : ""); b.textContent = t; b.title = d;
    b.onclick = () => saveHybrid({ orchestrate: v });
    $("hyOrch").appendChild(b);
  }
  $("hyAutoReplace").checked = h.auto_replace !== false;
  $("hyMem").checked = h.allow_memory; $("hyDocs").checked = h.allow_docs; $("hyWeb").checked = h.allow_web;
  const box = $("hyProviders");
  box.innerHTML = h.providers.length ? "" : '<p class="note">Aucun fournisseur configuré.</p>';
  for (const p of h.providers) {
    const row = document.createElement("div");
    row.className = "prov" + (p.id === h.provider ? " on" : "");
    const pct = Math.min(100, (100 * p.used_today) / Math.max(1, p.limit));
    row.innerHTML = `<div class="prov-top"><label class="prov-main"><input type="radio" name="hyPrimary" ${p.id === h.provider ? "checked" : ""}> <b>${esc(p.name)}</b></label>
        <span class="prov-tags"><span>${esc(p.family)}</span><span title="Force estimée (1 à 3)">${"●".repeat(p.strength)}${"○".repeat(3 - p.strength)}</span>${p.private ? "" : "<span>sans données privées</span>"}${p.paused ? "<span>en pause</span>" : ""}</span></div>
      <div class="row prov-model"><select class="field" aria-label="Modèle de ${esc(p.name)}"><option value="${esc(p.model)}">${esc(p.model)}</option><option value="__other">Autre… (saisir un nom)</option></select><input class="field" aria-label="Nom du modèle de ${esc(p.name)}" hidden value="${esc(p.model)}" spellcheck="false" autocomplete="off" placeholder="nom exact du modèle"><button class="btn sm">Enregistrer</button></div>
      <p class="note prov-note" hidden></p>
      <div class="metric"><div class="l"><span>${p.used_today} / ${p.limit} aujourd'hui</span><span></span></div><div class="bar"><i style="width:${pct}%"></i></div></div>`
      + (p.health && p.health.calls ? `<p class="note">Mesuré : ${p.health.latency != null ? p.health.latency + " s" : "—"} en moyenne · ${p.health.success ?? "—"} % de réussite sur les derniers appels${p.health.last_error ? ` · dernière erreur : ${esc(p.health.last_error.slice(0, 120))}` : ""}</p>` : "");
    row.querySelector("input").onchange = () => saveHybrid({ provider: p.id });
    const sel = row.querySelector("select"), inp = row.querySelector(".prov-model input"), note = row.querySelector(".prov-note");
    const showNote = (t) => { note.textContent = t; note.hidden = !t; };
    sel.onchange = () => { const other = sel.value === "__other"; inp.hidden = !other; sel.hidden = other; if (other) { inp.focus(); inp.select(); } };
    (async () => {   // liste chargée tout de suite, pour que le menu soit complet à l'ouverture
      try {
        const { models } = await getJSON(`/api/hybrid/models?provider=${encodeURIComponent(p.id)}`);
        if (!models.length) { showNote(`${p.name} ne publie pas de liste : choisis « Autre… » pour écrire le nom exact.`); return; }
        const missing = !models.includes(p.model);
        sel.innerHTML = (missing ? `<option value="${esc(p.model)}">${esc(p.model)} (introuvable)</option>` : "")
          + models.map((m) => `<option value="${esc(m)}" ${m === p.model ? "selected" : ""}>${esc(m)}</option>`).join("")
          + '<option value="__other">Autre… (saisir un nom)</option>';
        if (missing) showNote(`« ${p.model} » n'est plus proposé par ${p.name} : choisis un modèle dans la liste (${models.length} disponibles).`);
      } catch { showNote(`Liste des modèles indisponible : choisis « Autre… » pour écrire le nom exact.`); }
    })();
    row.querySelector("button").onclick = async () => {
      const model = (sel.hidden ? inp.value : sel.value).trim();
      if (!model || model === "__other") { inp.focus(); return; }
      try { hybridState = await (await api(`/api/hybrid/providers/${p.id}`, { method: "PUT", body: JSON.stringify({ model }) })).json(); toast(`${esc(p.name)} · modèle <b>${esc(model)}</b>`); }
      catch (e) { toast(esc(e.message)); }
      loadHybrid();
    };
    box.appendChild(row);
  }
  for (const x of h.skipped || []) box.insertAdjacentHTML("beforeend", `<div class="prov off"><div class="prov-top"><b style="font-weight:500">${esc(x.name)}</b><span class="prov-tags"><span>ignoré</span></span></div><p class="note" style="margin:6px 0 0">${esc(x.reason)} dans .env, puis <code>docker compose up -d atom</code>.</p></div>`);
  if (!h.providers_env) box.insertAdjacentHTML("beforeend", '<p class="note">Aucun fournisseur supplémentaire : ajoute par exemple <code>ATOM_CEREBRAS_API_KEY=…</code> dans <code>.env</code>, puis <code>docker compose up -d atom</code>.</p>');
}
async function saveHybrid(patch) {
  try { hybridState = await (await api("/api/hybrid", { method: "PUT", body: JSON.stringify(patch) })).json(); } catch (e) { toast(esc(e.message)); }
  loadHybrid();
}
$("hyMem").onchange = () => saveHybrid({ allow_memory: $("hyMem").checked });
$("hyDocs").onchange = () => saveHybrid({ allow_docs: $("hyDocs").checked });
$("hyWeb").onchange = () => saveHybrid({ allow_web: $("hyWeb").checked });

$("hyAutoReplace").onchange = () => saveHybrid({ auto_replace: $("hyAutoReplace").checked });
