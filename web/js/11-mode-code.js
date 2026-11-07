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

/* ---- modifications proposées : Atom propose, tu valides fichier par fichier */
function openEditBox(withSel) {
  const f = code.open.find((x) => x.path === code.active);
  if (!f) return;
  code.editRange = withSel && code.sel ? [...code.sel] : null;
  const n = f.content.split("\n").length;
  $("cvEditScope").textContent = code.editRange ? `Lignes ${code.editRange[0]} à ${code.editRange[1]}` : n > 400 ? "Fichier long : sélectionne d'abord des lignes" : "Fichier entier";
  const h = typeof hybridState !== "undefined" ? hybridState : null;
  $("cvRemoteWrap").hidden = !(h?.configured && h?.allow_docs);
  $("cvRemoteName").textContent = h ? `avec ${h.name}` : "";
  $("cvEditBox").hidden = false; $("cvInstr").focus();
}
$("cvEdit").onclick = () => openEditBox(false);
$("cvEditSel").onclick = () => openEditBox(true);
$("cvEditCancel").onclick = () => { $("cvEditBox").hidden = true; };
$("cvInstr").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("cvEditGo").click(); if (e.key === "Escape") $("cvEditBox").hidden = true; });
$("cvEditGo").onclick = async () => {
  const instruction = $("cvInstr").value.trim();
  if (instruction.length < 2) { $("cvInstr").focus(); return; }
  const btn = $("cvEditGo"); btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Atom réfléchit…';
  setEmotion("thinking"); entity.scan = true;
  const [start, end] = code.editRange || [null, null];
  try {
    const p = await (await send_(`/api/code/${code.project}/propose`, "POST", { path: code.active, instruction, start, end, engine: $("cvRemote").checked ? "remote" : "local" })).json();
    code.proposal = p; $("cvEditBox").hidden = true; $("cvInstr").value = "";
    setEmotion("idle");
    renderEditor();
  } catch (e) {
    setEmotion("idle"); entity.glitch = 1; toast(`<b>Modification</b> · ${esc(e.message)}`);
  } finally {
    btn.disabled = false; btn.textContent = "Proposer"; entity.scan = false;
  }
};
function renderDiff() {
  const p = code.proposal;
  $("cvDiffBar").hidden = false;
  $("cvDiffInfo").innerHTML = `Proposition · <b>+${p.added}</b> / <b>−${p.removed}</b>` + (p.by && p.by !== "local" ? ` · ${esc(p.by)}` : "");
  $("cvDiffApply").hidden = !p.writable;
  $("cvDiffApply").title = p.writable ? "Écrire la modification dans le clone local" : "";
  $("cvDiffPatch").title = p.writable ? "Télécharger le patch" : "Projet en lecture seule : télécharge le patch et applique-le avec git apply";
  const rows = p.diff.split("\n").filter((l, i) => !(i < 2 && (l.startsWith("---") || l.startsWith("+++"))));
  $("cvEditor").innerHTML = `<div class="cv-diff">${p.note ? `<div class="note-l">${esc(p.note)}</div>` : ""}${rows.map((l) =>
    `<div class="${l.startsWith("@@") ? "hunk" : l[0] === "+" ? "add" : l[0] === "-" ? "del" : ""}">${esc(l)}</div>`).join("")}</div>`;
}
function downloadPatch(text, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/x-diff" }));
  a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
$("cvDiffDrop").onclick = () => { code.proposal = null; renderEditor(); };
$("cvDiffPatch").onclick = () => { const p = code.proposal; if (p) downloadPatch(p.diff, p.path.split("/").pop() + ".patch"); };
$("cvDiffApply").onclick = async () => {
  const p = code.proposal; if (!p) return;
  let d;
  try { d = await (await send_(`/api/code/proposals/${p.id}/apply`, "POST")).json(); }
  catch (e) { toast(`<b>Modification</b> · ${esc(e.message)}`); return; }
  const f = code.open.find((x) => x.path === p.path); if (f) f.content = d.content;
  code.proposal = null; code.sel = null; entity.seal = 1;
  toast(`<b>${esc(p.path)}</b> · modification appliquée (clone local).`);
  renderEditor(); loadChanges();
};
function agoFr(ts) {
  const d = Date.now() / 1000 - ts;
  return d < 60 ? "à l'instant" : d < 3600 ? `il y a ${Math.round(d / 60)} min` : d < 86400 ? `il y a ${Math.round(d / 3600)} h` : `il y a ${Math.round(d / 86400)} j`;
}
// ---- Git : statut, branches, commit, push (chaque action = un clic de ta part)
async function loadChanges() {
  const box = $("cvChanges");
  let g;
  try { g = await getJSON(`/api/git/${code.project}/status`); } catch { box.hidden = true; code.git = null; $("cvGitNote").hidden = false; cvStatusUpdate(); return; }
  code.git = g; box.hidden = false; $("cvGitNote").hidden = true; cvStatusUpdate();
  const sel = code.gitSel || (code.gitSel = new Set());
  for (const f of g.files) if (!code.gitKnown?.has(f.path)) sel.add(f.path);   // nouveaux fichiers cochés par défaut
  code.gitKnown = new Set(g.files.map((f) => f.path));
  for (const p of [...sel]) if (!code.gitKnown.has(p)) sel.delete(p);
  const n = g.files.length;
  box.innerHTML = `
    <div class="h"><select class="git-br" id="gitBranch" title="Branche">${g.branches.map((b) => `<option ${b === g.branch ? "selected" : ""}>${esc(b)}</option>`).join("")}</select>
      <button id="gitNewBr" title="Nouvelle branche">＋ branche</button></div>
    <div class="git-st">${n ? `${n} fichier${n > 1 ? "s" : ""} modifié${n > 1 ? "s" : ""}` : "Aucune modification"}${g.ahead ? ` · <b>${g.ahead}</b> commit${g.ahead > 1 ? "s" : ""} à pousser` : ""}</div>
    ${g.files.map((f, i) => `<div class="f"><input type="checkbox" data-ck="${i}" ${sel.has(f.path) ? "checked" : ""}><span data-i2="${i}" title="${esc(f.path)} · ${esc(f.status)}">${esc(f.path)}</span><em>${esc(f.code)}</em><button data-rv="${i}" title="Revenir à la version du dépôt">Annuler</button></div>`).join("")}
    <div class="git-commit" id="gitCommitBox" ${code.gitCommitOpen && n ? "" : "hidden"}>
      <textarea class="field" id="gitMsg" rows="3" placeholder="Message du commit">${esc(code.gitMsg || "")}</textarea>
      <div class="row"><button class="btn sm" id="gitSuggest"><span data-i="spark"></span>Proposer</button><span class="spacer"></span><button class="btn sm" id="gitCancel">Annuler</button><button class="btn sm primary" id="gitDoCommit">Valider</button></div>
    </div>
    <div class="git-acts">
      ${n ? '<button class="btn sm" id="gitCommit">Commit…</button>' : ""}
      ${g.ahead ? `<button class="btn sm" id="gitPush" ${g.protected ? 'disabled title="Pas de push sur la branche principale : crée une branche"' : ""}>Pousser</button>` : ""}
      ${n ? '<button class="btn sm" id="gitPatch" title="Télécharger le patch des modifications">Patch</button>' : ""}
      ${n ? '<button class="btn sm" id="gitDiscard" title="Annuler toutes les modifications non commitées">Tout annuler</button>' : ""}
    </div>
    ${g.last ? `<div class="git-last" title="Dernier commit">${esc(g.last.hash)} · ${esc(g.last.subject)} · ${agoFr(g.last.when)}</div>` : ""}
    ${!g.token ? '<div class="git-last">Pour pousser : jeton GitHub avec droit d\'écriture dans .env (ATOM_GITHUB_TOKEN).</div>' : ""}`;
  const q = (x) => box.querySelector(x);
  box.querySelectorAll("[data-ck]").forEach((el) => { el.onchange = () => { const p = g.files[+el.dataset.ck].path; el.checked ? sel.add(p) : sel.delete(p); }; });
  box.querySelectorAll("[data-i2]").forEach((el) => { el.onclick = () => openFile(g.files[+el.dataset.i2].path); });
  box.querySelectorAll("[data-rv]").forEach((el) => {
    el.onclick = async () => {
      const path = g.files[+el.dataset.rv].path;
      if (!confirm(`Annuler les modifications de ${path} ?`)) return;
      try { await send_(`/api/code/${code.project}/revert`, "POST", { path }); } catch (e) { toast(esc(e.message)); }
      code.open = code.open.filter((x) => x.path !== path);
      if (code.active === path) { code.active = null; await openFile(path); }
      loadChanges();
    };
  });
  const gitDo = async (path, body, okMsg) => {
    try { const r = await (await send_(`/api/git/${code.project}/${path}`, "POST", body)).json(); if (okMsg) toast(okMsg(r)); return r; }
    catch (e) { toast(`<b>Git</b> · ${esc(e.message)}`); return null; }
    finally { await loadChanges(); }
  };
  const newBranch = async () => {
    const d = new Date(), def = `atom/${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}-${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")}`;
    const name = prompt("Nom de la nouvelle branche (tes modifications et commits non poussés la suivent) :", def);
    if (!name) return false;
    return !!(await gitDo("branch", { name: name.trim() }, (r) => `Branche <b>${esc(r.branch)}</b> créée.`));
  };
  q("#gitNewBr").onclick = newBranch;
  q("#gitBranch").onchange = async (e) => {
    const name = e.target.value;
    const r = await gitDo("switch", { name }, () => `Branche <b>${esc(name)}</b> · réindexation des fichiers changés…`);
    if (r) { markIndexing(code.project); code.open = []; code.active = null; code.proposal = null; renderTabs(); renderEditor(); loadLibrary(); setTimeout(loadCodeFiles, 1500); }
  };
  q("#gitCommit") && (q("#gitCommit").onclick = async () => {
    if (!sel.size) { toast("Coche au moins un fichier."); return; }
    code.gitCommitOpen = true;
    if (g.protected && confirm(`Tu es sur « ${g.branch} », où Atom ne pousse pas.\nCréer une branche de travail d'abord ?`)) { await newBranch(); }
    else { q("#gitCommitBox").hidden = false; }
    $("gitMsg")?.focus();
  });
  q("#gitCancel").onclick = () => { code.gitCommitOpen = false; code.gitMsg = ""; q("#gitCommitBox").hidden = true; };
  q("#gitMsg").oninput = (e) => { code.gitMsg = e.target.value; };
  q("#gitSuggest").onclick = async (e) => {
    const b = e.currentTarget; b.disabled = true; b.innerHTML = '<span class="spin"></span> Atom lit le diff…'; setEmotion("thinking");
    try { code.gitMsg = $("gitMsg").value = (await (await send_(`/api/git/${code.project}/message`, "POST", { paths: [...sel] })).json()).message; }
    catch (err) { toast(`<b>Git</b> · ${esc(err.message)}`); }
    finally { b.disabled = false; b.innerHTML = `${icon("spark")}Proposer`; setEmotion("idle"); }
  };
  q("#gitDoCommit").onclick = async () => {
    const message = $("gitMsg").value.trim();
    if (message.length < 3) { $("gitMsg").focus(); return; }
    code.gitCommitOpen = false; code.gitMsg = "";
    const ok = await gitDo("commit", { message, paths: [...sel] }, (r) => `Commit <b>${esc(r.last?.hash || "")}</b> créé · ${r.ahead} à pousser.`);
    if (ok) entity.seal = 1;
    else { code.gitCommitOpen = true; code.gitMsg = message; loadChanges(); }
  };
  q("#gitPush") && (q("#gitPush").onclick = async (e) => {
    if (!confirm(`Pousser ${g.ahead} commit${g.ahead > 1 ? "s" : ""} sur GitHub, branche « ${g.branch} » ?`)) return;
    e.currentTarget.disabled = true; e.currentTarget.innerHTML = '<span class="spin"></span> Envoi…';
    const r = await gitDo("push", undefined, null);
    if (r) {
      entity.seal = 1;
      toast(`<b>${esc(r.pushed)}</b> poussée sur GitHub.` + (r.compare ? ` <a href="${esc(r.compare)}" target="_blank" rel="noopener">Ouvrir une pull request</a>` : ""));
    }
  });
  q("#gitPatch") && (q("#gitPatch").onclick = async () => { try { downloadPatch((await getJSON(`/api/git/${code.project}/diff`)).diff, "atom-modifications.patch"); } catch (e) { toast(esc(e.message)); } });
  q("#gitDiscard") && (q("#gitDiscard").onclick = async () => {
    if (!confirm("Annuler toutes les modifications non commitées (fichiers nouveaux compris) ?")) return;
    if (await gitDo("discard", undefined, () => "Modifications annulées.")) { code.open = []; code.active = null; renderTabs(); renderEditor(); setTimeout(loadCodeFiles, 1200); }
  });
}

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
  $("agRecent").innerHTML = list.map((r) => `<button data-id="${r.id}"><span class="t">${esc(r.task)}</span><small>${ST[r.status] || r.status}</small>
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
