"use strict";

/* ============================================================
   ZONE DE SAISIE — outils derrière « + », modes actifs en pastilles
   (divulgation progressive : l'essentiel visible, le reste à un clic)
   ============================================================ */
function toolsItems() {
  const items = [];
  if (searchAvailable) {
    items.push({ id: "web", ic: "globe", t: "Rechercher sur Internet", d: "Pour ce message · quelques secondes", on: webForce, run: () => $("webBtn").click() });
    items.push({ id: "deep", ic: "library", t: "Recherche approfondie", d: "Plan, lecture de nombreuses pages, rapport sourcé · 1 à 3 min", on: deepNext, run: () => $("deepBtn").click() });
  }
  if (workshopCfg?.enabled) items.push({ id: "ws", ic: "users", t: "Atelier multi-IA", d: "Plusieurs IA rédigent et se relisent · 3 appels ou plus", on: workshopNext, run: () => $("wsBtn").click() });
  items.push("hr");
  items.push({ id: "file", ic: "clip", t: "Joindre un fichier", d: "Texte, code, PDF, tableur (analysé en Python), image", run: () => $("attach").click() });
  items.push({ id: "pal", ic: "search", t: "Toutes les actions", d: "Ctrl+K", run: () => openPalette() });
  return items;
}
function renderTools() {
  $("toolsMenu").innerHTML = toolsItems().map((x, i) => x === "hr" ? "<hr>" :
    `<button type="button" data-k="${i}" class="${x.on ? "on" : ""}">${icon(x.ic)}<b>${esc(x.t)}</b><small>${esc(x.d)}</small></button>`).join("");
  const items = toolsItems();
  $("toolsMenu").querySelectorAll("[data-k]").forEach((b) => { b.onclick = () => { $("toolsMenu").classList.remove("open"); items[+b.dataset.k].run(); renderModes(); }; });
}
$("toolsBtn").onclick = (e) => { e.stopPropagation(); renderTools(); $("toolsMenu").classList.toggle("open"); };
document.addEventListener("click", (e) => { if (!e.target.closest(".tools-wrap")) $("toolsMenu").classList.remove("open"); });
function renderModes() {
  const m = [];
  if (webForce) m.push(["globe", "Recherche web", () => $("webBtn").click()]);
  if (deepNext) m.push(["library", "Recherche approfondie · 1 à 3 min", () => $("deepBtn").click()]);
  if (workshopNext) m.push(["users", "Atelier multi-IA", () => $("wsBtn").click()]);
  const box = $("modes");
  const key = m.map((x) => x[1]).join("|");
  if (box.dataset.k === key) return;
  box.dataset.k = key;
  box.innerHTML = m.map(([ic, t], i) => `<span class="mode-chip">${icon(ic)}${esc(t)}<button type="button" data-x="${i}" title="Désactiver">${icon("x")}</button></span>`).join("");
  box.querySelectorAll("[data-x]").forEach((b) => { b.onclick = () => { m[+b.dataset.x][2](); renderModes(); input.focus(); }; });
  $("toolsBtn").classList.toggle("on", m.length > 0);
}
setInterval(renderModes, 400);

/* ============================================================
   THÈME
   ============================================================ */
const darkMQ = matchMedia("(prefers-color-scheme: dark)");
function applyTheme() {
  const t = settings.theme || "dark";
  const eff = t === "auto" ? (darkMQ.matches ? "dark" : "light") : t;
  document.documentElement.dataset.theme = eff;
  document.querySelector('meta[name="theme-color"]').content = eff === "light" ? "#f6f6f3" : "#1b1b1b";
}
darkMQ.addEventListener?.("change", applyTheme);
choiceRow("themeRow", "theme", [["dark", "Sombre"], ["light", "Clair"], ["auto", "Automatique"]]);
const _applyLook = applyLook;
applyLook = function () { _applyLook(); applyTheme(); };
document.body.classList.toggle("no-hero", settings.heroWelcome === false);
$("heroToggle").checked = settings.heroWelcome !== false;
$("heroToggle").onchange = () => { settings.heroWelcome = $("heroToggle").checked; saveSettings(); document.body.classList.toggle("no-hero", !settings.heroWelcome); if (!settings.heroWelcome) exitHero(); else if (!history.length) enterHero(); };

/* ============================================================
   PALETTE DE COMMANDES (Ctrl+K)
   ============================================================ */
let palItems = [], palSel = 0, palTimer = 0;
function palActions() {
  const A = (g, ic, label, run, hint = "") => ({ g, ic, label, run, hint });
  const list = [
    A("Actions", "plus", "Nouvelle conversation", () => newConversation(), "Ctrl ⇧ O"),
    A("Actions", "orb", "Mode présence", () => enterPresence()),
    A("Canevas", "doc", "Nouveau canevas (document vide)", () => newCanvas("Nouveau document", "")),
    ...(palCanvases || []).map((c) => A("Canevas", "doc", `Ouvrir le canevas « ${c.title} »`, () => openCanvas(c.id))),
    A("Espaces", "folder", "Nouvel espace…", () => openSpaceDlg(null)),
    ...spacesList.map((x) => A("Espaces", "folder", `Ouvrir l'espace « ${x.name} »`, () => enterSpace(x.id))),
    ...(currentConv() ? spacesList.map((x) => A("Espaces", "folder", `Ranger cette conversation dans « ${x.name} »`, () => moveToSpace(x.id))) : []),
    ...(currentConv()?.space_id ? [A("Espaces", "folder", "Retirer cette conversation de son espace", () => moveToSpace(null))] : []),
    A("Actions", "globe", webForce ? "Ne plus forcer la recherche web" : "Rechercher sur Internet pour le prochain message", () => { webForce = !webForce; renderWebBtn(); }),
    A("Actions", "download", "Exporter la conversation en Markdown", () => $("exportBtn").click()),
    A("Aller à", "list", "Discussion", () => showView("chat")),
    A("Aller à", "library", "Bibliothèque", () => showView("library")),
    A("Aller à", "code", "Code", () => showView("code")),
    A("Apparence", "panel", (document.documentElement.dataset.theme === "light" ? "Thème sombre" : "Thème clair"), () => { settings.theme = document.documentElement.dataset.theme === "light" ? "dark" : "light"; saveSettings(); applyTheme(); choiceRow("themeRow", "theme", [["dark", "Sombre"], ["light", "Clair"], ["auto", "Automatique"]]); }),
    A("Apparence", "sidebar", "Afficher / masquer la barre latérale", () => $("sideClose").click()),
    A("Apparence", "panel", "Afficher / masquer le panneau de l'entité", () => $("panelBtn").click()),
  ];
  if (hybridState?.configured) for (const [v, t] of [["local", "Local"], ["auto", "Auto"], ["mistral", hybridState.name]]) list.push(A("Moteur", v === "local" ? "orb" : "spark", `Répondre avec : ${t}`, () => setEngine(v)));
  if (workshopCfg?.enabled) list.push(A("Actions", "users", "Atelier multi-IA pour le prochain message", () => { workshopNext = true; $("wsBtn").classList.add("on"); }));
  for (const o of [...modelSel.options]) if (o.value) list.push(A("Modèle", "spark", `Modèle : ${o.value}`, () => { modelSel.value = o.value; modelSel.onchange(); }));
  for (const t of document.querySelectorAll(".tabs .tab")) list.push(A("Réglages", "settings", `Réglages · ${t.textContent.trim()}`, () => openSettings(t.dataset.tab)));
  list.push(A("Compte", "lock", "Me déconnecter", () => $("secLogout").click()));
  return list;
}
function fuzzy(q, text) {
  if (!q) return { score: 1, html: esc(text) };
  const t = text.toLowerCase(), ql = q.toLowerCase();
  const at = t.indexOf(ql);
  if (at >= 0) return { score: 100 - at, html: esc(text.slice(0, at)) + `<mark>${esc(text.slice(at, at + q.length))}</mark>` + esc(text.slice(at + q.length)) };
  let j = 0, out = "", score = 0;
  for (let i = 0; i < text.length; i++) {
    if (j < ql.length && t[i] === ql[j]) { out += `<mark>${esc(text[i])}</mark>`; j++; score += 2; } else out += esc(text[i]);
  }
  return j === ql.length ? { score, html: out } : null;
}
async function palRender() {
  const q = $("palIn").value.trim();
  const items = [];
  for (const c of conversations.slice(0, 200)) {
    const m = fuzzy(q, c.title); if (m) items.push({ g: "Conversations", ic: c.pinned ? "pin" : "list", html: m.html, score: m.score + (q ? 5 : 0), hint: groupOf(c.updated_at), run: () => openConversation(c.id) });
  }
  if (currentView === "code" && q.length >= 2) for (const f of code.files) { const m = fuzzy(q, f.path); if (m) items.push({ g: "Fichiers du projet", ic: "doc", html: m.html, score: m.score, run: () => openFile(f.path) }); }
  for (const c of library.collections || []) { const m = fuzzy(q, c.name); if (m && q) items.push({ g: "Bibliothèque", ic: c.kind === "code" ? "code" : "folder", html: m.html, score: m.score, run: () => { showView(c.kind === "code" ? "code" : "library"); if (c.kind === "code") { code.project = c.id; loadCodeProjects(); } else { libSel = c.id; renderLibrary(); } } }); }
  for (const a of palActions()) { const m = fuzzy(q, a.label); if (m) items.push({ g: a.g, ic: a.ic, html: m.html, score: m.score, hint: a.hint, run: a.run }); }
  const order = ["Conversations", "Actions", "Aller à", "Fichiers du projet", "Bibliothèque", "Moteur", "Modèle", "Apparence", "Réglages", "Compte"];
  items.sort((a, b) => q ? b.score - a.score : order.indexOf(a.g) - order.indexOf(b.g));
  const top = q ? items.slice(0, 40) : [...items.filter((x) => x.g === "Conversations").slice(0, 5), ...items.filter((x) => x.g !== "Conversations").slice(0, 14)];
  // recherche dans le contenu des conversations
  if (q.length >= 3) {
    clearTimeout(palTimer);
    palTimer = setTimeout(async () => {
      try {
        const r = (await getJSON("/api/search?q=" + encodeURIComponent(q))).results.filter((c) => !top.some((x) => x.g === "Conversations" && x.html.replace(/<[^>]+>/g, "") === c.title));
        if (!r.length || $("palIn").value.trim() !== q) return;
        palItems = [...palItems, ...r.slice(0, 8).map((c) => ({ g: "Dans les messages", ic: "search", html: esc(c.title) + (c.snippet ? ` <small style="margin-left:6px;color:var(--faint);font-family:var(--sans)">${esc(c.snippet.slice(0, 60))}</small>` : ""), run: () => openConversation(c.id) }))];
        palDraw();
      } catch {}
    }, 220);
  }
  palItems = top; palSel = 0; palDraw();
}
function palDraw() {
  const box = $("palList");
  box.innerHTML = "";
  let g = null;
  palItems.forEach((it, k) => {
    if (it.g !== g) { g = it.g; box.insertAdjacentHTML("beforeend", `<div class="pal-g">${esc(g)}</div>`); }
    const b = document.createElement("button");
    b.className = "pal-i" + (k === palSel ? " sel" : "");
    b.innerHTML = `${icon(it.ic)}<span>${it.html}</span>${it.hint ? `<small>${esc(it.hint)}</small>` : ""}`;
    b.onmouseenter = () => { palSel = k; box.querySelectorAll(".pal-i").forEach((x, n) => x.classList.toggle("sel", n === k)); };
    b.onclick = () => palRun(k);
    box.appendChild(b);
  });
  if (!palItems.length) box.innerHTML = '<div class="side-empty">Aucun résultat.</div>';
}
function palRun(k) { const it = palItems[k]; closePalette(); it?.run(); }
function openPalette() { $("palette").classList.add("open"); $("palIn").value = ""; palRender(); setTimeout(() => $("palIn").focus(), 20); }
function closePalette() { $("palette").classList.remove("open"); }
$("palIn").addEventListener("input", palRender);
$("palIn").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    palSel = (palSel + (e.key === "ArrowDown" ? 1 : -1) + palItems.length) % Math.max(1, palItems.length);
    $("palList").querySelectorAll(".pal-i").forEach((x, n) => { x.classList.toggle("sel", n === palSel); if (n === palSel) x.scrollIntoView({ block: "nearest" }); });
  } else if (e.key === "Enter") { e.preventDefault(); palRun(palSel); }
  else if (e.key === "Escape") { e.preventDefault(); closePalette(); }
});
$("palette").addEventListener("click", (e) => { if (e.target.id === "palette") closePalette(); });

/* ============================================================
   MOBILE : barre d'onglets et gestes
   ============================================================ */
function syncTabbar() {
  const on = app.classList.contains("panel-open") ? "atom" : app.classList.contains("side-open") ? "chats" : currentView === "chat" ? "chats" : currentView;
  document.querySelectorAll("#tabbar button").forEach((b) => b.classList.toggle("on", b.dataset.tab === on));
}
document.querySelectorAll("#tabbar button").forEach((b) => b.onclick = () => {
  const t = b.dataset.tab;
  app.classList.remove("panel-open");
  if (t === "chats") { if (currentView !== "chat") { showView("chat"); app.classList.remove("side-open"); } else app.classList.toggle("side-open"); }
  else if (t === "library" || t === "code") { app.classList.remove("side-open"); showView(t); }
  else if (t === "atom") { app.classList.remove("side-open"); app.classList.add("panel-open"); refreshPanel(); refreshSystem(); }
  else if (t === "settings") { app.classList.remove("side-open"); openSettings(); }
  applyLayout(); syncTabbar();
});
new MutationObserver(syncTabbar).observe(app, { attributes: true, attributeFilter: ["class"] });
syncTabbar();
(() => {
  let sx = 0, sy = 0, edge = null, t0 = 0;
  addEventListener("touchstart", (e) => {
    if (!narrow() || e.touches.length !== 1) return;
    const x = e.touches[0].clientX; sx = x; sy = e.touches[0].clientY; t0 = Date.now();
    edge = app.classList.contains("side-open") ? "closeSide" : app.classList.contains("panel-open") ? "closePanel"
      : x < 28 ? "left" : x > innerWidth - 28 ? "right" : null;
  }, { passive: true });
  addEventListener("touchend", (e) => {
    if (!edge) return;
    const t = e.changedTouches[0], dx = t.clientX - sx, dy = t.clientY - sy;
    if (Math.abs(dy) > Math.abs(dx) || Date.now() - t0 > 700) { edge = null; return; }
    if (edge === "left" && dx > 60) app.classList.add("side-open");
    else if (edge === "right" && dx < -60) { app.classList.add("panel-open"); refreshPanel(); }
    else if (edge === "closeSide" && dx < -60) app.classList.remove("side-open");
    else if (edge === "closePanel" && dx > 60) app.classList.remove("panel-open");
    edge = null; applyLayout();
  }, { passive: true });
})();

/* ============================================================
   GLISSER-DÉPOSER : message, bibliothèque, ou directement dans l'entité
   ============================================================ */
function dropContext() {
  if (currentView === "library") {
    const c = library.collections.find((x) => x.id === libSel && x.kind === "docs") || library.collections.find((x) => x.kind === "docs");
    return ["Ajouter à la bibliothèque", c ? `Collection « ${c.name} » · Atom lira et indexera tes documents` : "Bibliothèque"];
  }
  if (currentView === "code") return ["Les projets s'ajoutent depuis GitHub ou un dossier", "Utilise « Ajouter un projet » : un dépôt n'est pas un simple fichier"];
  return ["Joindre au message", "Ou dépose-les sur l'entité pour les ranger dans ta bibliothèque"];
}
addEventListener("dragenter", (e) => {
  if (![...(e.dataTransfer?.types || [])].includes("Files")) return;
  const [t, s2] = dropContext(); $("dropTitle").textContent = t; $("dropSub").textContent = s2;
  entity.feedColor = [235, 235, 240]; entity.hover = true; entity.typingAt = performance.now();
});
stageEl.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); stageEl.classList.add("dropover"); entity.feeding = true; });
stageEl.addEventListener("dragleave", () => { stageEl.classList.remove("dropover"); entity.feeding = false; });
stageEl.addEventListener("drop", async (e) => {
  e.preventDefault(); e.stopPropagation();
  stageEl.classList.remove("dropover"); $("drop").classList.remove("on"); dragDepth = 0;
  const files = [...(e.dataTransfer?.files || [])];
  if (!files.length) return;
  if (!library.collections.length) { try { library = await getJSON("/api/library"); } catch {} }
  const c = library.collections.find((x) => x.kind === "docs");
  if (c) { entity.absorb = 1; uploadDocs(c.id, files); } else toast("Aucune collection de documents.");
});
addEventListener("dragleave", () => { if (!dragDepth) { entity.hover = false; } });
