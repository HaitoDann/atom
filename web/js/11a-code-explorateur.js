"use strict";

/* ============================================================
   MODE CODE — parcourir un projet, lire ses fichiers
   ============================================================ */
const code = { project: null, files: [], open: [], active: null, sel: null, proposal: null, editRange: null, changes: null, expanded: new Set([""]), grep: false };
const LANG = (p) => {
  const n = p.toLowerCase(), ext = n.includes(".") ? n.split(".").pop() : n.split("/").pop();
  return ({ py: "py", sh: "sh", bash: "sh", zsh: "sh", yml: "yaml", yaml: "yaml", toml: "toml", ini: "ini", cfg: "ini", conf: "ini", env: "ini",
    rb: "rb", js: "js", mjs: "js", cjs: "js", jsx: "js", ts: "js", tsx: "js", vue: "html", svelte: "html", json: "json",
    c: "c", h: "c", cpp: "c", hpp: "c", cc: "c", cs: "c", java: "c", kt: "c", go: "c", rs: "c", swift: "c", dart: "c", scala: "c", php: "c",
    css: "css", scss: "css", sass: "css", less: "css", html: "html", htm: "html", xml: "html", svg: "html",
    sql: "sql", lua: "sql", hs: "sql", md: "md", markdown: "md", dockerfile: "sh", makefile: "sh", tf: "sh", hcl: "sh", nix: "sh", r: "sh" })[ext] || "txt";
};
const COMMENT = { py: "#", sh: "#", yaml: "#", toml: "#", ini: "[#;]", rb: "#", js: "//", c: "//", css: null, sql: "--", json: null, html: null, md: null, txt: null };

/* Coloration par langage : commentaires, chaînes, nombres, mots-clés, fonctions, décorateurs, balises. */
function highlightLang(src, lang) {
  if (lang === "txt" || lang === "md") return esc(src);
  const lc = COMMENT[lang];
  const parts = [];
  if (lang === "html") parts.push("(<!--[\\s\\S]*?-->)");
  else if (["js", "c", "css"].includes(lang)) parts.push("(\\/\\*[\\s\\S]*?\\*\\/" + (lc ? "|" + lc + "[^\\n]*" : "") + ")");
  else if (lc) parts.push("(" + lc + "[^\\n]*)");
  else parts.push("(\\u0000)");
  parts.push(lang === "py" ? "(\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''|\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*')"
    : "(\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*'|`(?:\\\\.|[^`\\\\])*`)");
  parts.push("\\b(\\d+(?:\\.\\d+)?)\\b");
  parts.push(lang === "html" ? "(<\\/?[A-Za-z][\\w-]*|\\/?>)" : lang === "css" ? "(#[0-9a-fA-F]{3,8}\\b|@[\\w-]+)" : "(@[A-Za-z_][\\w.]*)");
  parts.push("\\b([A-Za-z_]\\w*)(?=\\s*\\()");
  parts.push("\\b([A-Za-z_][\\w-]*)\\b");
  const re = new RegExp(parts.join("|"), "g");
  let out = "", last = 0, m;
  while ((m = re.exec(src))) {
    if (!m[0]) { re.lastIndex++; continue; }
    out += esc(src.slice(last, m.index));
    const [tok, com, str, num, deco, fn, word] = m;
    if (com && com !== "\u0000") out += `<span class="tk-c">${esc(com)}</span>`;
    else if (str) out += `<span class="tk-s">${esc(str)}</span>`;
    else if (num) out += `<span class="tk-n">${num}</span>`;
    else if (deco) out += `<span class="tk-d">${esc(deco)}</span>`;
    else if (fn) out += KW.has(fn) ? `<span class="tk-k">${fn}</span>` : `<span class="tk-f">${fn}</span>`;
    else if (word) out += KW.has(word) ? `<span class="tk-k">${word}</span>` : (lang === "json" || lang === "yaml") && /^[A-Za-z]/.test(word) && src[m.index + word.length] === ":" ? `<span class="tk-f">${word}</span>` : esc(word);
    else out += esc(tok);
    last = m.index + tok.length;
  }
  return out + esc(src.slice(last));
}

// État du mode Code conservé entre deux chargements (F5) : projet, onglets, fichier actif, agent ouvert.
let codeRestored = false;
function saveCodeState() {
  if (!codeRestored) return;
  store.set("codeState", { project: code.project, open: code.open.map((f) => f.path), active: code.active, pane: cvPane });
}
async function loadCodeProjects() {
  try { library = await getJSON("/api/library"); } catch { return; }
  const projects = library.collections.filter((c) => c.kind === "code");
  const saved = !codeRestored ? store.get("codeState", null) : null;
  if (saved && projects.some((p) => p.id === saved.project)) code.project = saved.project;
  const sel = $("cvProject");
  sel.innerHTML = projects.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
  $("cvEmpty").hidden = projects.length > 0;
  $("cvMainWrap").hidden = projects.length === 0;
  if (!projects.length) return;
  if (!projects.some((p) => p.id === code.project)) code.project = projects[0].id;
  sel.value = code.project;
  await loadCodeFiles();
  if (saved && saved.project === code.project && !code.open.length) {
    for (const path of (saved.open || []).slice(-8)) if (code.files.some((f) => f.path === path)) await openFile(path);
    if (saved.pane) cvSetPane(saved.pane);
    if (saved.active && code.open.some((f) => f.path === saved.active)) { code.active = saved.active; renderTabs(); renderEditor(); renderTree(); }
    else { codeRestored = true; agOpen(); }
    codeRestored = true;
  } else if (!code.open.length) agOpen();
  codeRestored = true;
  if (projects.some((p) => p.status === "indexing")) { clearTimeout(libTimer); libTimer = setTimeout(loadLibrary, 2000); }
}
$("cvProject").onchange = async () => { if (!$("cvAgentView").hidden) agClose(); agRun = null; $("agLog").innerHTML = ""; $("agRes").hidden = true; code.project = +$("cvProject").value; code.open = []; code.proposal = null; code.gitSel = null; code.gitKnown = null; code.active = "__agent"; code.expanded = new Set([""]); await loadCodeFiles(); renderTabs(); renderEditor(); agOpen(); saveCodeState(); };

async function loadCodeFiles() {
  const d = await getJSON(`/api/library/collections/${code.project}/documents`);
  loadChanges(); loadSandbox();
  code.files = d.documents.map((x) => ({ path: x.path, size: x.size })).sort((a, b) => a.path.localeCompare(b.path));
  const c = d.collection;
  renderCodeInfo({ ...c, progress: library.collections.find((x) => x.id === c.id)?.progress });
  renderTree();
}

function renderTree() {
  const box = $("cvTree");
  const q = $("cvFilter").value.trim().toLowerCase();
  box.innerHTML = "";
  if (code.grep && q.length >= 2) return runGrep(q);
  if (q) {
    for (const f of code.files.filter((f) => f.path.toLowerCase().includes(q)).slice(0, 300)) box.appendChild(fileRow(f.path, f.path, 0));
    if (!box.children.length) box.innerHTML = '<div class="side-empty">Aucun fichier.</div>';
    return;
  }
  // arbre : dossiers repliables
  const tree = {};
  for (const f of code.files) {
    const parts = f.path.split("/");
    let node = tree;
    parts.forEach((p, i) => { if (i === parts.length - 1) (node.__files ||= []).push(f.path); else node = (node[p] ||= {}); });
  }
  const walk = (node, prefix, depth) => {
    for (const k of Object.keys(node).filter((k) => k !== "__files").sort()) {
      const path = prefix ? `${prefix}/${k}` : k;
      const open = code.expanded.has(path);
      const r = document.createElement("button");
      r.className = "cv-row dir"; r.style.paddingLeft = 8 + depth * 14 + "px";
      r.innerHTML = `<span class="car">${open ? "▾" : "▸"}</span>${icon("folder")}<span>${esc(k)}</span>`;
      r.onclick = () => { open ? code.expanded.delete(path) : code.expanded.add(path); renderTree(); };
      box.appendChild(r);
      if (open) walk(node[k], path, depth + 1);
    }
    for (const p of (node.__files || []).sort()) box.appendChild(fileRow(p, p.split("/").pop(), depth));
  };
  walk(tree, "", 0);
}
function fileRow(path, label, depth) {
  const r = document.createElement("button");
  r.className = "cv-row" + (code.active === path ? " on" : "");
  r.style.paddingLeft = 22 + depth * 14 + "px";
  r.title = path;
  r.innerHTML = `${icon("doc")}<span>${esc(label)}</span>`;
  r.onclick = () => openFile(path);
  return r;
}
async function runGrep(q) {
  const box = $("cvTree");
  box.innerHTML = '<div class="side-empty"><span class="spin"></span> Recherche…</div>';
  let r;
  try { r = await getJSON(`/api/library/collections/${code.project}/grep?q=${encodeURIComponent(q)}`); } catch { return; }
  box.innerHTML = r.matches.length ? "" : '<div class="side-empty">Aucun résultat.</div>';
  for (const m of r.matches) {
    const b = document.createElement("button");
    b.className = "cv-hit";
    const i = m.text.toLowerCase().indexOf(q);
    const t = i >= 0 ? esc(m.text.slice(0, i)) + `<mark>${esc(m.text.slice(i, i + q.length))}</mark>` + esc(m.text.slice(i + q.length)) : esc(m.text);
    b.innerHTML = `<small>${esc(m.path)}:${m.line}</small><code>${t}</code>`;
    b.onclick = () => openFile(m.path, m.line);
    box.appendChild(b);
  }
}
let grepTimer = 0;
$("cvFilter").addEventListener("input", () => { clearTimeout(grepTimer); grepTimer = setTimeout(renderTree, code.grep ? 300 : 0); });
$("cvGrep").onclick = () => { code.grep = !code.grep; $("cvGrep").classList.toggle("on", code.grep); $("cvFilter").placeholder = code.grep ? "Chercher dans le contenu…" : "Filtrer les fichiers…"; renderTree(); $("cvFilter").focus(); };

async function openFile(path, line) {
  let f = code.open.find((x) => x.path === path);
  if (!f) {
    try {
      const r = await getJSON(`/api/library/collections/${code.project}/file?path=${encodeURIComponent(path)}`);
      f = { path, content: r.content, md: false };
    } catch { toast("Fichier introuvable (projet à mettre à jour ?)."); return; }
    code.open.push(f);
    if (code.open.length > 8) code.open.shift();
  }
  code.active = path; code.sel = line ? [line, line] : null;
  renderTabs(); renderEditor(line); renderTree(); saveCodeState();
  entity.scan = true; clearTimeout(openFile._t); openFile._t = setTimeout(() => { entity.scan = false; }, 1400);
}
function closeTab(path) {
  code.open = code.open.filter((x) => x.path !== path);
  if (code.active === path) code.active = code.open.at(-1)?.path || "__agent";
  code.sel = null; renderTabs(); renderEditor(); renderTree(); saveCodeState();
}
function renderTabs() {
  const t = $("cvTabs");
  t.innerHTML = "";
  const home = document.createElement("div");
  home.className = "cv-tab home" + (code.active === "__agent" || !code.active ? " on" : "");
  home.title = "Agent : confier une tâche ou poser une question sur le projet";
  home.innerHTML = `${icon("spark")}<span>Agent</span>`;
  home.onclick = () => agOpen();
  t.appendChild(home);
  for (const f of code.open) {
    const b = document.createElement("div");
    b.className = "cv-tab" + (f.path === code.active ? " on" : "");
    b.title = f.path;
    b.innerHTML = `<span>${esc(f.path.split("/").pop())}</span>`;
    const x = document.createElement("button"); x.innerHTML = icon("x"); x.title = "Fermer";
    x.onclick = (e) => { e.stopPropagation(); closeTab(f.path); };
    b.onclick = () => { code.active = f.path; code.sel = null; renderTabs(); renderEditor(); renderTree(); };
    b.appendChild(x); t.appendChild(b);
  }
}
const MAX_LINES = 8000;
function renderEditor(scrollLine) {
  const isHome = code.active === "__agent" || !code.active;
  $("cvAgentView").hidden = !isHome; $("cvMainWrap").hidden = isHome;
  cvStatusUpdate();
  if (isHome) return;
  const f = code.open.find((x) => x.path === code.active);
  $("cvBar").hidden = !f; $("cvSelBar").hidden = true;
  if (code.proposal && code.proposal.path === f?.path) return renderDiff();
  $("cvDiffBar").hidden = true;
  const ed = $("cvEditor");
  if (!f) { ed.innerHTML = '<div class="cv-placeholder">Choisis un fichier dans l\'arborescence.<small>Clique sur les numéros de ligne (Maj+clic pour une plage) pour demander à Atom d\'expliquer un passage.</small></div>'; return; }
  const lines = f.content.split("\n");
  const shown = lines.slice(0, MAX_LINES);
  const lang = LANG(f.path);
  $("cvPath").textContent = f.path;
  $("cvMeta").textContent = `${lines.length} lignes · ${lang.toUpperCase()}`;
  $("cvMd").hidden = lang !== "md";
  $("cvMd").classList.toggle("on", f.md);
  if (lang === "md" && f.md) { ed.innerHTML = `<div class="cv-md md">${md(f.content)}</div>`; renderMath(ed); return; }
  ed.innerHTML = `<div class="cv-code"><div class="cv-gutter">${shown.map((_, i) => `<span data-l="${i + 1}">${i + 1}</span>`).join("")}</div><div class="cv-src"><div class="cv-hl" id="cvHl"></div><pre class="cv"><code>${highlightLang(shown.join("\n"), lang)}</code></pre></div></div>`
    + (lines.length > MAX_LINES ? `<div class="note" style="padding:10px 16px">Fichier long : seules les ${MAX_LINES} premières lignes sont affichées.</div>` : "");
  ed.querySelector(".cv-gutter").onclick = (e) => {
    const l = +e.target.dataset.l; if (!l) return;
    code.sel = e.shiftKey && code.sel ? [Math.min(code.sel[0], l), Math.max(code.sel[1], l)] : [l, l];
    paintSel();
  };
  paintSel(); cvStatusUpdate();
  if (scrollLine) requestAnimationFrame(() => { const lh = lineH(); ed.scrollTop = Math.max(0, (scrollLine - 6) * lh); });
}
const lineH = () => parseFloat(getComputedStyle(document.querySelector(".cv") || document.body).lineHeight) || 19;
function paintSel() {
  const hl = $("cvHl");
  if (!hl) return;
  document.querySelectorAll(".cv-gutter span.on").forEach((x) => x.classList.remove("on"));
  if (!code.sel) { hl.style.display = "none"; $("cvSelBar").hidden = true; return; }
  const [a, b] = code.sel, lh = lineH();
  Object.assign(hl.style, { display: "block", top: 12 + (a - 1) * lh + "px", height: (b - a + 1) * lh + "px" });
  for (let i = a; i <= b; i++) document.querySelector(`.cv-gutter span[data-l="${i}"]`)?.classList.add("on");
  $("cvSelBar").hidden = false;
  $("cvSelInfo").textContent = a === b ? `Ligne ${a}` : `Lignes ${a} à ${b}`;
}
function selectionText() {
  const f = code.open.find((x) => x.path === code.active);
  if (!f) return "";
  const [a, b] = code.sel || [1, f.content.split("\n").length];
  return f.content.split("\n").slice(a - 1, b).join("\n");
}
function askAtom(prompt, withSel) {
  const f = code.open.find((x) => x.path === code.active);
  if (!f) return;
  setScope(String(code.project));
  const [a, b] = code.sel || [];
  const name = withSel && code.sel ? `${f.path} (l. ${a}-${b})` : f.path;
  const text = withSel && code.sel ? selectionText() : f.content.slice(0, 12000);
  showView("chat"); newConversation();
  pending = [{ name, text }]; renderTray();
  fillInput(prompt);
}
$("cvExplain").onclick = () => askAtom("Explique-moi ces lignes : ce qu'elles font et pourquoi.", true);
$("cvReview").onclick = () => askAtom("Relis ces lignes : bugs possibles, cas oubliés, améliorations.", true);
$("cvAskSel").onclick = () => askAtom("", true);
$("cvAsk").onclick = () => askAtom("Explique-moi ce fichier : son rôle dans le projet et son fonctionnement.", false);
$("cvCopy").onclick = (e) => flashCopy(e.currentTarget, code.open.find((x) => x.path === code.active)?.content || "");
$("cvCopyPath").onclick = () => { copyText(code.active || ""); toast("Chemin copié."); };
$("cvMd").onclick = () => { const f = code.open.find((x) => x.path === code.active); if (f) { f.md = !f.md; renderEditor(); } };
$("cvSync").onclick = async () => { await send_(`/api/library/collections/${code.project}/sync`, "POST"); markIndexing(code.project); toast("Mise à jour du projet lancée."); loadLibrary(); };
$("cvAdd").onclick = () => { library.server_projects ||= []; $("libNewCode").onclick(); };
$("cvAdd2").onclick = () => $("cvAdd").onclick();
