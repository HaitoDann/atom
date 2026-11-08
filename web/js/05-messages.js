"use strict";

/* ============================================================
   MESSAGES
   ============================================================ */
const chat = $("chat"), scroller = $("scroller"), input = $("input"), sendBtn = $("send"), form = $("form");

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Bonne nuit." : h < 12 ? "Bonjour." : h < 18 ? "Bon après-midi." : "Bonsoir.";
}
// Suggestions d'accueil adaptées à ce qui est configuré (bibliothèque, projets, recherche web).
const BASE_SUGGESTIONS = [
  { i: "clock", t: "Programmer un rappel", d: "« Rappelle-moi demain à 9 h de… »", fill: "Rappelle-moi demain à 9 h de " },
  { i: "doc", t: "Rédiger un texte", d: "Mail, message, résumé…", fill: "Rédige un mail court pour " },
  { i: "user", t: "Ce que tu sais de moi", d: "Voir ce qu'Atom a retenu", send: "Qu'est-ce que tu sais de moi ?" },
  { i: "scale", t: "Comparer deux options", d: "Un tableau clair des avantages", fill: "Compare dans un tableau " },
];
function suggestions() {
  const cols = (typeof library !== "undefined" && library?.collections) || [];
  const ready = cols.filter((c) => c.status !== "error" && c.chunks > 0);
  const docs = ready.filter((c) => c.kind !== "code"), code = ready.filter((c) => c.kind === "code");
  const out = [];
  if (docs.length) {
    const c = docs[Math.floor(Math.random() * docs.length)];
    out.push({ i: "library", t: "Interroger ta bibliothèque", d: `Dans « ${c.name} »`, fill: "D'après mes documents, ", scope: String(c.id) });
  }
  if (code.length) {
    const c = code[Math.floor(Math.random() * code.length)];
    out.push({ i: "code", t: `Explique ${c.name}`, d: "Architecture et fichiers clés", send: `Explique-moi l'architecture du projet ${c.name} : rôle des dossiers et fichiers principaux.`, scope: String(c.id) });
  }
  if (typeof searchAvailable !== "undefined" && searchAvailable)
    out.push({ i: "globe", t: "Chercher sur Internet", d: "Actualité, prix, horaires…", fill: "Cherche sur Internet ", web: true });
  for (const s of BASE_SUGGESTIONS) if (out.length < 4) out.push(s);
  return out;
}

function renderCards() {
  const cards = chat.querySelector("#empty .cards");
  if (!cards) return;
  cards.innerHTML = "";
  suggestions().forEach((s, k) => {
    const b = document.createElement("button");
    b.className = "card"; b.style.setProperty("--i", k);
    if (s.scope || s.web) b.dataset.cap = 1;
    b.innerHTML = `<b>${icon(s.i)}${esc(s.t)}</b><span>${esc(s.d)}</span>`;
    b.onclick = () => {
      if (s.scope) setScope(s.scope);
      if (s.web) { webForce = true; renderWebBtn(); }
      s.send ? sendMessage(s.send) : fillInput(s.fill);
    };
    cards.appendChild(b);
  });
}

function renderEmpty() {
  const g = greeting().replace(/\.$/, "");
  chat.innerHTML = `<div id="empty"><div id="heroSlot"></div><h1><span class="orbtxt">${g}</span>.</h1><p>Que puis-je faire pour toi ?</p><div class="today" id="today"></div><div class="cards"></div></div>`;
  renderCards();
  renderToday();
  requestAnimationFrame(() => enterHero());
}

function fillInput(text) { input.value = text; autoGrow(); input.focus(); input.setSelectionRange(text.length, text.length); }

function msgEl(m, idx, fresh = false) {
  const el = document.createElement("div");
  const isUser = m.role === "user";
  el.className = "msg " + (m.error ? "err" : isUser ? "user" : "atom") + (fresh ? " fresh" : "");
  el.dataset.idx = idx;
  const files = m.meta?.attachments;
  if (isUser && files?.length) {
    const f = document.createElement("div");
    f.className = "files";
    for (const a of files) f.appendChild(fileChip(a));
    el.appendChild(f);
  }
  const body = document.createElement("div");
  body.className = "body" + (isUser ? "" : " md");
  if (isUser || m.error) body.textContent = m.content; else { setMd(body, m.content); addZipBar(body); }
  if (isUser && !m.content) body.style.display = "none";
  el.appendChild(body);
  if (!isUser && m.meta?.workshop) { el.insertBefore(workshopPipe(m.meta.workshop), body); el.insertBefore(workshopEl(m.meta.workshop), body); }
  if (!isUser && m.meta?.docs?.length) el.appendChild(docsEl(m.meta.docs));
  if (!isUser && m.meta?.reminders?.length) for (const r of m.meta.reminders) el.appendChild(reminderCard(r));
  if (!isUser && m.meta?.analysis) el.appendChild(analysisEl(m.meta.analysis));
  if (!isUser && m.meta?.research) body.insertAdjacentHTML("beforebegin", `<div class="rs-tag">${icon("library")}Recherche approfondie · ${m.meta.research.queries?.length || 0} recherches · ${m.meta.sources?.length || 0} sources${m.meta.research.engine ? ` · ${esc(m.meta.research.engine)}` : ""}</div>`);
  if (!isUser && m.meta?.sources?.length) el.appendChild(sourcesEl(m.meta.sources));
  if (!isUser && m.meta?.used) el.appendChild(usedEl(m.meta.used));
  if (!m.error) el.appendChild(actions(m, idx));
  return el;
}

function fileChip(a, onRemove) {
  const c = document.createElement("span");
  c.className = "file" + (a.loading ? " loading" : "");
  const size = a.loading ? "lecture…" : a.data ? "analyse Python" : a.pages ? `${a.pages} p.` : `${Math.max(1, Math.round((a.chars ?? a.text?.length ?? 0) / 1000))} k car.`;
  c.innerHTML = `${icon("doc")}<b>${esc(a.name)}</b><small>${size}</small>`;
  if (onRemove) {
    const x = document.createElement("button");
    x.type = "button"; x.title = "Retirer"; x.innerHTML = icon("x");
    x.onclick = onRemove;
    c.appendChild(x);
  }
  return c;
}

function sourcesEl(list) {
  const d = document.createElement("div");
  d.className = "src-cards sources";
  list.slice(0, 6).forEach((x, i) => {
    const a = document.createElement("a");
    a.className = "src-card src-l"; a.href = x.url; a.target = "_blank"; a.rel = "noopener noreferrer"; a.title = x.title;
    a.innerHTML = `<div class="d"><i>${i + 1}</i>${esc(x.domain)}</div><b>${esc(x.title)}</b>${x.snippet ? `<p>${esc(x.snippet)}</p>` : ""}`;
    d.appendChild(a);
  });
  return d;
}

/* Carte de rappel dans le fil : date, texte, annulation */
let pendingReminders = null;
async function pendingIds() {
  if (!pendingReminders) pendingReminders = getJSON("/api/reminders").then((r) => new Set(r.reminders.map((x) => x.id))).catch(() => new Set());
  return pendingReminders;
}
function reminderCard(r) {
  const c = document.createElement("div");
  c.className = "acard";
  const cancelled = r.action === "cancelled";
  c.innerHTML = `<span class="ic">${icon("clock")}</span><div class="tx"><b>${esc(cancelled ? `Rappel #${r.id} annulé` : r.text || "Rappel")}</b><small>${esc(cancelled ? "" : r.when || "")}</small></div>`;
  if (!cancelled) {
    const b = document.createElement("button"); b.className = "btn sm"; b.textContent = "Annuler";
    b.onclick = async () => {
      try { await send_(`/api/reminders/${r.id}`, "DELETE"); } catch { toast("Ce rappel a déjà été envoyé ou annulé."); }
      pendingReminders = null; c.classList.add("done"); b.remove(); c.querySelector("small").textContent = "annulé"; refreshPanel();
    };
    c.appendChild(b);
    pendingIds().then((ids) => { if (!ids.has(r.id)) { c.classList.add("done"); b.remove(); c.querySelector("small").textContent += " · passé ou annulé"; } });
  } else c.classList.add("done");
  return c;
}
function memoryCard(list) {
  const c = document.createElement("div");
  c.className = "acard";
  const txt = list.map((m) => m.content.replace(/^L'utilisateur\s+/i, "")).join(" · ");
  c.innerHTML = `<span class="ic">${icon("memory")}</span><div class="tx"><b>Retenu</b><small>${esc(txt)}</small></div>`;
  const b = document.createElement("button"); b.className = "btn sm"; b.textContent = "Oublier";
  b.onclick = async () => { for (const m of list) { try { await send_(`/api/memories/${m.id}`, "DELETE"); } catch {} } c.classList.add("done"); b.remove(); c.querySelector("b").textContent = "Oublié"; refreshPanel(); };
  c.appendChild(b);
  return c;
}

/* 4. Base de la réponse : sources web, bibliothèque, ou rien (à vérifier si ça ressemble à un fait précis) */
function basisEl(m) {
  const s = document.createElement("span");
  const nW = m.meta?.sources?.length || 0, nD = m.meta?.docs?.length || 0;
  if (nW || nD) {
    s.className = "basis";
    const parts = [];
    if (nD) parts.push(`${nD} passage${nD > 1 ? "s" : ""} de ta bibliothèque`);
    if (nW) parts.push(`${nW} source${nW > 1 ? "s" : ""} web`);
    s.innerHTML = icon("check") + "Basé sur " + esc(parts.join(" et "));
    return s;
  }
  const factual = /\b(1[6-9]|20)\d{2}\b|\d+[,.]?\d*\s?(€|\$|%|km|kg|go|to|mo|°)|\b\d{3,}\b/i.test(m.content || "");
  if (factual && (m.content || "").length > 60) {
    s.className = "basis warn"; s.title = "Atom a répondu de mémoire, sans document ni recherche : vérifie les chiffres et les dates.";
    s.innerHTML = "Sans source · à vérifier";
    return s;
  }
  return null;
}

/* « 2 souvenirs utilisés » : ce qu'Atom a pris en compte pour répondre */
function usedEl(used) {
  const facts = used.facts || [], recall = used.recall || [];
  const d = document.createElement("details");
  d.className = "used";
  const parts = [];
  if (facts.length) parts.push(`${facts.length} souvenir${facts.length > 1 ? "s" : ""}`);
  if (recall.length) parts.push(`${recall.length} ancienne${recall.length > 1 ? "s" : ""} conversation${recall.length > 1 ? "s" : ""}`);
  d.innerHTML = `<summary>${icon("memory")}${parts.join(" · ")} utilisé${facts.length + recall.length > 1 ? "s" : ""}</summary><ul></ul>`;
  const ul = d.querySelector("ul");
  for (const f of facts) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${esc(f.content)}</span>`;
    const b = document.createElement("button");
    b.textContent = "Oublier"; b.title = "Supprimer ce souvenir";
    b.onclick = async () => {
      try { await send_(`/api/memories/${f.id}`, "DELETE"); li.style.opacity = ".4"; li.querySelector("span").style.textDecoration = "line-through"; b.remove(); refreshPanel(); }
      catch { toast("Souvenir déjà supprimé."); }
    };
    li.appendChild(b);
    ul.appendChild(li);
  }
  for (const r of recall) {
    const li = document.createElement("li");
    li.innerHTML = `<span><small>Conversation passée · </small>${esc(r.text.slice(0, 160))}${r.text.length > 160 ? "…" : ""}</span>`;
    if (r.conversation_id) {
      const b = document.createElement("button");
      b.textContent = "Ouvrir";
      b.onclick = () => openConversation(r.conversation_id);
      li.appendChild(b);
    }
    ul.appendChild(li);
  }
  return d;
}

function actions(m, idx) {
  const a = document.createElement("div");
  a.className = "acts";
  const btn = (name, title, fn) => {
    const b = document.createElement("button");
    b.className = "iconbtn"; b.title = title; b.innerHTML = icon(name);
    b.onclick = fn; a.appendChild(b); return b;
  };
  if (m.role === "user") {
    if (m.created_at) { const t = document.createElement("time"); t.textContent = fmtTime(m.created_at); a.appendChild(t); }
    btn("copy", "Copier", (e) => flashCopy(e.currentTarget, m.content));
    if (m.id) btn("edit", "Modifier", () => editMessage(idx));
  } else {
    btn("copy", "Copier", (e) => flashCopy(e.currentTarget, m.content));
    btn("doc", "Ouvrir dans le canevas (modifier avec Atom)", () => canvasFromMessage(m));
    if (idx === history.length - 1) btn("refresh", "Régénérer", () => regenerate());
    if (idx === history.length - 1 && !m.meta?.provider && hybridState?.configured) btn("spark", `Réponse approfondie (${hybridState.name})`, () => regenerate("mistral"));
    if (m.id) {
      const up = btn("up2", "Bonne réponse", () => vote(m, 1, up, dn, a));
      const dn = btn("down2", "Mauvaise réponse", () => vote(m, -1, up, dn, a));
      up.classList.toggle("voted", m.feedback === 1); dn.classList.toggle("voted", m.feedback === -1);
    }
    if (m.created_at) { const t = document.createElement("time"); t.textContent = fmtTime(m.created_at); a.appendChild(t); }
    const bs = basisEl(m); if (bs) a.appendChild(bs);
    if (m.meta?.provider) { const v = document.createElement("span"); v.className = "via"; v.textContent = "via " + m.meta.provider; v.title = m.meta.remote_model || ""; a.appendChild(v); }
  }
  return a;
}

async function vote(m, value, up, dn, bar) {
  const v = m.feedback === value ? null : value;
  try { await send_(`/api/messages/${m.id}`, "PATCH", { value: v }); } catch { return; }
  m.feedback = v;
  up.classList.toggle("voted", v === 1); dn.classList.toggle("voted", v === -1);
  bar.parentElement.querySelector(".reason")?.remove();
  if (v === -1) {
    const r = document.createElement("div");
    r.className = "reason";
    r.innerHTML = '<input class="field" placeholder="Qu\'est-ce qui n\'allait pas ? (facultatif)"><button class="btn">Envoyer</button>';
    const inp = r.querySelector("input");
    const go = async () => { if (inp.value.trim()) await send_(`/api/messages/${m.id}`, "PATCH", { value: -1, reason: inp.value.trim() }); r.remove(); toast("Merci, c'est noté."); };
    r.querySelector("button").onclick = go;
    inp.onkeydown = (e) => { if (e.key === "Enter") go(); if (e.key === "Escape") r.remove(); };
    bar.after(r); inp.focus();
  } else if (v === 1) toast("Merci !");
}

function flashCopy(btn, text) {
  copyText(text);
  btn.innerHTML = icon("check");
  setTimeout(() => { btn.innerHTML = icon("copy"); }, 1300);
}

function renderHistory() {
  chat.innerHTML = "";
  if (!history.length) { renderEmpty(); return; }
  exitHero();
  history.forEach((m, i) => chat.appendChild(msgEl(m, i)));
  markLast();
  scroller.scrollTop = scroller.scrollHeight;
}
function markLast() {
  chat.querySelectorAll(".msg.last").forEach((x) => x.classList.remove("last"));
  const lastAtom = [...chat.querySelectorAll(".msg.atom")].pop();
  if (lastAtom && lastAtom === chat.lastElementChild) lastAtom.classList.add("last");
}

chat.addEventListener("click", async (e) => {
  const dl = e.target.closest("[data-dl]"), pv = e.target.closest("[data-preview]");
  if (dl || pv) {
    const box = (dl || pv).closest(".code"), code = box.querySelector("pre").textContent;
    if (dl) {
      const name = box.dataset.name || "fichier.txt";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([code], { type: name.endsWith(".html") ? "text/html" : "text/plain" }));
      a.download = name; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast(`${esc(name)} téléchargé.`);
    } else openPreview(code, box.dataset.name || "page.html", box);
    return;
  }
  const b = e.target.closest("[data-copy]");
  if (!b) return;
  copyText(b.closest(".code").querySelector("pre").innerText);
  const old = b.innerHTML;
  b.innerHTML = icon("check") + "Copié";
  setTimeout(() => { b.innerHTML = old; }, 1300);
});

function editMessage(idx) {
  if (busy) return;
  const m = history[idx];
  const el = chat.querySelector(`.msg[data-idx="${idx}"]`);
  const box = document.createElement("div");
  box.className = "edit-box";
  box.innerHTML = `<textarea></textarea><div class="row"><button class="btn" data-a="cancel">Annuler</button><button class="btn primary" data-a="send">Envoyer</button></div>`;
  const ta = box.querySelector("textarea");
  ta.value = m.content;
  el.innerHTML = ""; el.appendChild(box);
  ta.style.height = ta.scrollHeight + "px"; ta.focus();
  box.querySelector('[data-a="cancel"]').onclick = () => renderHistory();
  box.querySelector('[data-a="send"]').onclick = async () => {
    const v = ta.value.trim();
    if (!v) return;
    await send_(`/api/conversations/${settings.conversationId}/truncate`, "POST", { from_id: m.id });
    history = history.slice(0, idx);
    renderHistory();
    sendMessage(v);
  };
  ta.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); box.querySelector('[data-a="send"]').click(); } if (e.key === "Escape") renderHistory(); };
}

async function regenerate(withEngine) {
  if (busy) return;
  let i = history.length - 1;
  while (i >= 0 && history[i].role !== "user") i--;
  if (i < 0 || !history[i].id) return;
  const text = history[i].content;
  await send_(`/api/conversations/${settings.conversationId}/truncate`, "POST", { from_id: history[i].id });
  history = history.slice(0, i);
  renderHistory();
  if (withEngine) engineOverride = withEngine;
  sendMessage(text);
}

/* scroll */
function atBottom() { return scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 60; }
scroller.addEventListener("scroll", () => {
  $("toBottom").classList.toggle("on", !atBottom());
  $("topbar").classList.toggle("scrolled", scroller.scrollTop > 4);
});
$("toBottom").onclick = () => scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });


/* Aperçu d'une page HTML : servie par Atom dans un bac à sable (origine isolée), affichée dans un cadre. */
let pvw = { name: "", versions: [], idx: 0 };
async function openPreview(html, name, box) {
  // Toutes les versions de ce fichier dans la conversation, dans l'ordre : on peut passer de l'une à l'autre.
  const blocks = [...chat.querySelectorAll(".code")].filter((b) => (b.dataset.name || "page.html") === name);
  pvw = { name, versions: blocks.map((b) => b.querySelector("pre").textContent), idx: Math.max(0, blocks.indexOf(box)) };
  if (!pvw.versions.length) pvw.versions = [html];
  $("pvwTitle").textContent = name;
  $("pvwVers").innerHTML = pvw.versions.length > 1 ? pvw.versions.map((_, i) => `<button type="button" data-v="${i}">v${i + 1}</button>`).join("") : "";
  $("pvwVers").querySelectorAll("button").forEach((b) => b.onclick = () => showPreviewVersion(+b.dataset.v));
  $("pvw").hidden = false;
  await showPreviewVersion(pvw.idx);
  $("pvwAskIn").value = "";
}
async function showPreviewVersion(i) {
  pvw.idx = i;
  const html = pvw.versions[i];
  $("pvwVers").querySelectorAll("button").forEach((b) => b.classList.toggle("on", +b.dataset.v === i));
  let r;
  try { r = await (await send_("/api/preview", "POST", { html })).json(); } catch (e) { toast(esc(e.message)); return; }
  $("pvwFrame").src = r.url;
  $("pvwOpen").onclick = () => window.open(r.url, "_blank", "noopener");
  $("pvwDl").onclick = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([html], { type: "text/html" })); a.download = pvw.name; a.click(); };
}
// Itérer : la version affichée et ta consigne partent dans la conversation ; la nouvelle version arrive en réponse.
$("pvwAsk").addEventListener("submit", (e) => {
  e.preventDefault();
  const ask = $("pvwAskIn").value.trim(); if (!ask || busy) return;
  const lang = /\.css$/.test(pvw.name) ? "css" : /\.js$/.test(pvw.name) ? "js" : "html";
  closePreview();
  input.value = `Modifie le fichier **${pvw.name}** : ${ask}\n\nGarde tout le reste à l'identique et renvoie le fichier COMPLET, ` +
    `précédé de son nom (**${pvw.name}**).\n\nVersion actuelle (v${pvw.idx + 1}) :\n\n**${pvw.name}**\n\n\`\`\`${lang}\n${pvw.versions[pvw.idx]}\n\`\`\``;
  autoGrow(); sendBtn.click();
});
function closePreview() { $("pvw").hidden = true; $("pvwFrame").src = "about:blank"; }
$("pvwClose").onclick = closePreview;
$("pvw").addEventListener("click", (e) => { if (e.target.id === "pvw") closePreview(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("pvw").hidden) closePreview(); });
document.querySelectorAll("#pvw .seg button").forEach((b) => b.onclick = () => {
  document.querySelectorAll("#pvw .seg button").forEach((x) => x.classList.toggle("on", x === b));
  $("pvwFrame").style.width = b.dataset.w;
});


/* ---- Plusieurs fichiers dans une réponse : tout télécharger en .zip (format zip « stocké », sans dépendance). */
const CRC_TABLE = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(b) { let c = 0xffffffff; for (let i = 0; i < b.length; i++) c = CRC_TABLE[(c ^ b[i]) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }
function makeZip(files) {
  const enc = new TextEncoder(), parts = [], central = [];
  let offset = 0;
  const d = new Date(), time = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
    date = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
  for (const f of files) {
    const name = enc.encode(f.name), data = enc.encode(f.text), crc = crc32(data);
    const h = new DataView(new ArrayBuffer(30));
    [[0, 0x04034b50, 4], [4, 20, 2], [6, 0x0800, 2], [8, 0, 2], [10, time, 2], [12, date, 2], [14, crc, 4], [18, data.length, 4],
     [22, data.length, 4], [26, name.length, 2], [28, 0, 2]].forEach(([o, v, n]) => n === 4 ? h.setUint32(o, v, true) : h.setUint16(o, v, true));
    const c = new DataView(new ArrayBuffer(46));
    [[0, 0x02014b50, 4], [4, 20, 2], [6, 20, 2], [8, 0x0800, 2], [10, 0, 2], [12, time, 2], [14, date, 2], [16, crc, 4], [20, data.length, 4],
     [24, data.length, 4], [28, name.length, 2], [30, 0, 2], [32, 0, 2], [34, 0, 2], [36, 0, 2], [38, 0, 4], [42, offset, 4]]
      .forEach(([o, v, n]) => n === 4 ? c.setUint32(o, v, true) : c.setUint16(o, v, true));
    parts.push(h, name, data); central.push(c, name);
    offset += 30 + name.length + data.length;
  }
  const size = central.reduce((a, x) => a + (x.byteLength ?? x.length), 0);
  const end = new DataView(new ArrayBuffer(22));
  [[0, 0x06054b50, 4], [4, 0, 2], [6, 0, 2], [8, files.length, 2], [10, files.length, 2], [12, size, 4], [16, offset, 4], [20, 0, 2]]
    .forEach(([o, v, n]) => n === 4 ? end.setUint32(o, v, true) : end.setUint16(o, v, true));
  return new Blob([...parts, ...central, end], { type: "application/zip" });
}
function zipFiles(body) {
  const seen = {};
  return [...body.querySelectorAll(".code[data-name]")].filter((b) => b.dataset.name).map((b) => {
    let name = b.dataset.name;
    if (seen[name]) { seen[name]++; name = name.replace(/(\.[^.]+)?$/, `-${seen[name]}$1`); } else seen[name] = 1;   // noms en double
    return { name, text: b.querySelector("pre").textContent };
  });
}
function addZipBar(body) {
  const files = zipFiles(body);
  if (!files.length) return;
  const bar = document.createElement("div"); bar.className = "zip-bar";
  bar.innerHTML = `<span>${files.length > 1 ? `${files.length} fichiers` : "1 fichier"} : ${files.map((f) => `<code>${esc(f.name)}</code>`).join(" ")}</span>` +
    `<button class="btn sm" data-project title="Enregistrer comme projet et l'ouvrir dans le mode Code (modifier, versions Git, agent, tests)">${icon("code")}Ouvrir dans le mode Code</button>` +
    (files.length > 1 ? `<button class="btn sm" data-zip>${icon("download")}Tout télécharger (.zip)</button>` : "");
  bar.querySelector("[data-project]").onclick = (e) => saveAsProject(e.currentTarget, zipFiles(body));
  if (files.length < 2) { body.appendChild(bar); return; }
  bar.querySelector("[data-zip]").onclick = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(makeZip(zipFiles(body)));
    a.download = (files.find((f) => f.name.endsWith(".html"))?.name.replace(/\.html?$/, "") || "fichiers") + ".zip";
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast(`${files.length} fichiers téléchargés (.zip).`);
  };
  body.appendChild(bar);
}


/* Les fichiers d'une réponse deviennent un projet du mode Code : on peut alors les modifier (avec validation),
   garder des versions Git, lancer l'agent ou les tests. */
async function saveAsProject(btn, files) {
  const html = files.find((f) => /\.html?$/.test(f.name));
  const title = html?.text.match(/<title>([^<]{1,60})<\/title>/i)?.[1]?.trim();
  const name = prompt("Nom du projet :", title || files[0].name.replace(/\.[^.]+$/, ""));
  if (!name) return;
  btn.disabled = true;
  try {
    const r = await (await send_("/api/projects/from-files", "POST", { name, files: files.map((f) => ({ path: f.name, content: f.text })) })).json();
    toast(`Projet « ${esc(name)} » créé (${r.files} fichier${r.files > 1 ? "s" : ""}).`);
    code.project = r.collection_id; code.open = []; codeRestored = true;
    showView("code");
    await loadCodeProjects();
    const main = html?.name || files[0].name;
    if (code.files.some((f) => f.path === main)) await openFile(main);
  } catch (e) { toast(esc(e.message)); }
  finally { btn.disabled = false; }
}
