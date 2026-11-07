"use strict";

/* ============================================================
   CONNEXION
   ============================================================ */
const modelSel = $("model");
let online = false;
async function connect(verbose = false) {
  let info = "", ok = false, err = false;
  try {
    const h = await getJSON("/api/health");
    ok = h.ollama && h.model_ready;
    info = h.provider === "mock" ? "Mode test"
      : !h.ollama ? "Ollama injoignable"
      : !h.model_ready ? "Aucun modèle installé"
      : "En ligne";
    err = !h.ollama;
    const details = [
      h.provider === "mock" ? "Mode test, sans modèle." : h.ollama ? "Ollama joignable." : "Ollama injoignable depuis le serveur.",
      h.embeddings ? "Mémoire sémantique active." : "Mémoire sans recherche sémantique (nomic-embed-text absent).",
      h.telegram ? "Telegram activé." : "Telegram désactivé.",
      h.search ? "Recherche web disponible." : "Recherche web désactivée.",
    ];
    searchAvailable = !!h.search; renderWebBtn(); if (searchAvailable && !document.querySelector("#empty .card[data-cap]")) renderCards();
    $("webInfo").textContent = h.search ? "" : "Le service de recherche (SearXNG) n'est pas configuré sur le serveur.";
    $("srvInfo").textContent = details.join(" ");
    if (h.ollama) {
      const m = await getJSON("/api/models");
      const prev = modelSel.value;
      modelSel.innerHTML = "";
      if (!m.models.length) modelSel.add(new Option("Aucun modèle", ""));
      for (const n of m.models) modelSel.add(new Option(n, n));
      if (!m.models.includes(settings.model)) { settings.model = m.models.includes(m.default) ? m.default : (m.models[0] || ""); saveSettings(); }
      const c = currentConv();
      modelSel.value = (c?.model && m.models.includes(c.model)) ? c.model : (settings.model || prev);
    }
  } catch {
    info = "Serveur injoignable"; err = true;
    $("srvInfo").textContent = "Le serveur Atom ne répond pas.";
  }
  if (!modelSel.options.length) modelSel.add(new Option(settings.model || "Hors ligne", settings.model));
  online = ok;
  $("dot").className = "dot" + (ok ? " on" : err ? " err" : "");
  $("statusText").textContent = info;
  if (verbose) toast(esc($("srvInfo").textContent));
}
modelSel.onchange = () => {
  settings.model = modelSel.value; saveSettings();
  const c = currentConv();
  toast(c ? `Modèle de cette conversation : <b>${esc(modelSel.value)}</b>` : `Modèle : <b>${esc(modelSel.value)}</b>`);
};

/* ============================================================
   FICHIERS JOINTS (glisser-déposer, coller, bouton trombone)
   ============================================================ */
let pending = [];   // [{name, text, pages, loading}]
function renderTray() {
  const tray = $("tray");
  tray.innerHTML = "";
  pending.forEach((f, i) => tray.appendChild(fileChip(f, () => { pending.splice(i, 1); renderTray(); })));
  autoGrow();
}
function toBase64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",")[1] || "");
    r.onerror = rej;
    r.readAsDataURL(file);
  });
}
async function addFiles(list) {
  for (const file of list) {
    if (pending.length >= 5) { toast("5 fichiers maximum par message."); break; }
    if (file.size > 15 * 1024 * 1024) { toast(`<b>${esc(file.name)}</b> · trop gros (15 Mo max).`); continue; }
    if (/\.(csv|tsv|xlsx|xls|json|parquet)$/i.test(file.name) && sbGlobal?.enabled) {
      // fichier de données : analysé par Python dans le bac à sable (le fichier ne quitte pas le serveur)
      const item = { name: file.name, text: "", loading: true, data: true, chars: file.size };
      pending.push(item); renderTray();
      try { item.b64 = await toBase64(file); item.loading = false; } catch { pending.splice(pending.indexOf(item), 1); }
      renderTray();
      if (pending.filter((f) => f.data).length === 1) toast(`<b>${esc(file.name)}</b> · pose ta question : Atom l'analysera avec Python (graphiques compris).`);
      continue;
    }
    const item = { name: file.name, text: "", loading: true };
    pending.push(item); renderTray();
    try {
      const r = await (await api("/api/extract", { method: "POST", body: JSON.stringify({ name: file.name, data: await toBase64(file) }) })).json();
      Object.assign(item, { text: r.text, pages: r.pages, loading: false });
      if (r.text.length > 12000) toast(`<b>${esc(file.name)}</b> · long fichier : seuls les 12 000 premiers caractères seront lus.`);
    } catch (e) {
      pending.splice(pending.indexOf(item), 1);
      toast(`<b>${esc(file.name)}</b> · ${esc(e.message)}`);
    }
    renderTray();
  }
  input.focus();
}
$("attach").onclick = () => $("fileIn").click();
$("fileIn").onchange = (e) => { addFiles([...e.target.files]); e.target.value = ""; };
let dragDepth = 0;
addEventListener("dragenter", (e) => { if ([...(e.dataTransfer?.types || [])].includes("Files")) { dragDepth++; $("drop").classList.add("on"); } });
addEventListener("dragleave", () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $("drop").classList.remove("on"); });
addEventListener("dragover", (e) => e.preventDefault());
addEventListener("drop", (e) => {
  e.preventDefault(); dragDepth = 0; $("drop").classList.remove("on");
  if (!e.dataTransfer?.files?.length) return;
  if (!$("libView").hidden) {
    const c = library.collections.find((x) => x.id === libSel && x.kind === "docs") || library.collections.find((x) => x.kind === "docs");
    if (c) uploadDocs(c.id, [...e.dataTransfer.files]);
    return;
  }
  addFiles([...e.dataTransfer.files]);
});
input.addEventListener("paste", (e) => {
  const files = [...(e.clipboardData?.files || [])];
  if (files.length) { e.preventDefault(); addFiles(files); }
});

/* ============================================================
   BROUILLONS (un par conversation)
   ============================================================ */
const draftKey = () => "draft." + (settings.conversationId || "new");
let draftTimer = 0;
function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    try { input.value ? localStorage.setItem("atom." + draftKey(), input.value) : localStorage.removeItem("atom." + draftKey()); } catch {}
  }, 250);
}
function clearDraft() { clearTimeout(draftTimer); try { localStorage.removeItem("atom." + draftKey()); } catch {} }
function restoreDraft() {
  let v = "";
  try { v = localStorage.getItem("atom." + draftKey()) || ""; } catch {}
  input.value = v; autoGrow();
}

/* ============================================================
   APPARENCE (densité, largeur)
   ============================================================ */
function applyLook() {
  document.body.classList.toggle("compact", settings.density === "compact");
  document.body.classList.toggle("wide", settings.width === "wide");
  document.body.classList.toggle("narrow", settings.width === "narrow");
}
function choiceRow(id, key, options) {
  const row = $(id);
  row.innerHTML = "";
  for (const [val, label] of options) {
    const b = document.createElement("button");
    b.className = "btn" + ((settings[key] || options[0][0]) === val ? " primary" : "");
    b.textContent = label;
    b.onclick = () => { settings[key] = val; saveSettings(); applyLook(); choiceRow(id, key, options); };
    row.appendChild(b);
  }
}
choiceRow("densityRow", "density", [["comfort", "Confortable"], ["compact", "Compacte"]]);
choiceRow("styleRow", "entityStyle", [["mesh", "Maillage"], ["fragments", "Fragments"], ["orb", "Planète"]]);
choiceRow("widthRow", "width", [["normal", "Normale"], ["narrow", "Étroite"], ["wide", "Large"]]);

/* ============================================================
   HUMEUR (teinte de repos) et rythme jour / nuit
   ============================================================ */
async function refreshMood() {
  let data;
  try { data = await getJSON("/api/mood?hours=24"); } catch { return; }
  let w = 0, v = 0;
  for (const e of data.events) { const k = Math.pow(0.5, (data.now - e.created_at) / 10800); w += k; v += k * (VALENCE[e.emotion] ?? 0); }
  entity.mood = w ? v / w * Math.min(1, w) : 0;
}
function checkNight() {
  const h = new Date().getHours();
  entity.night = h >= 23 || h < 6;
}

/* ============================================================
   MODE PRÉSENCE — la sphère quitte son panneau et occupe l'écran.
   Le canvas passe en plein écran d'un coup (invisible : la sphère est
   dessinée au même endroit), puis c'est le dessin qui glisse et grandit,
   sur une seule courbe. Aucun redimensionnement pendant l'animation.
   ============================================================ */
const stageEl = $("stage");
let presenceOn = false, presenceBusy = false, placeholder = null, wakeLock = null, clockTimer = 0;

function tickClock() {
  const d = new Date();
  $("pClock").textContent = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  $("pDate").textContent = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  $("pEmoBig").textContent = ACTIVITIES[entity.activity].label.toLowerCase();
}
function presenceSay(text, label = "Atom") {
  if (!text) return;
  const plain = text.replace(/```[\s\S]*?```/g, "[code]").replace(/[#*_`>|]/g, "").replace(/\s+/g, " ").trim();
  $("pSay").innerHTML = `<small>${esc(label)}</small>${esc(plain.length > 220 ? plain.slice(0, 217) + "…" : plain)}`;
}

entity.panelRect = () => {
  if (placeholder && placeholder.isConnected) {
    const r = placeholder.getBoundingClientRect();
    if (r.width > 10) return r;
  }
  const b = $("presenceBtn").getBoundingClientRect();   // panneau fermé : la sphère naît du bouton
  return { left: b.left, top: b.top, width: b.width, height: b.height };
};

function flyTo(to, dur, onEnd) {
  const f = entity.fly;
  Object.assign(f, { from: f.p, to, start: performance.now(), dur, active: true, onEnd });
}

let heroOn = false, heroBusy = false;
function stageOut(cls) {
  placeholder = document.createElement("div");
  placeholder.className = "stage-ph" + (cls ? " " + cls : "");
  placeholder.style.height = stageEl.offsetHeight + "px";
  stageEl.after(placeholder);
  document.body.appendChild(stageEl);
  stageEl.classList.add("flying");
  entity.flying = true;
}
function stageBack() {
  stageEl.classList.remove("flying");
  entity.flying = false;
  placeholder?.replaceWith(stageEl);
  placeholder = null;
}
entity.heroRect = () => $("heroSlot")?.getBoundingClientRect() || null;
function enterHero() {
  if (settings.heroWelcome === false || heroOn || heroBusy || presenceOn || presenceBusy || currentView !== "chat") return;
  if (!$("heroSlot") || narrow()) return;
  heroBusy = true; heroOn = true;
  entity.target = "hero";
  stageOut("hero-ph");
  document.body.classList.add("hero");
  requestAnimationFrame(() => { if (placeholder) placeholder.style.height = "0px"; });   // le panneau remonte ses rubriques
  flyTo(1, 1000, () => { heroBusy = false; });
}
function exitHero(cb) {
  if (!heroOn) { cb && cb(); return; }
  heroBusy = true;
  document.body.classList.remove("hero");
  if (placeholder) placeholder.style.height = "360px";   // la place revient pendant le retour de l'entité
  flyTo(0, 750, () => { stageBack(); heroOn = false; heroBusy = false; entity.target = "full"; cb && cb(); });
}

async function enterPresence() {
  if (heroOn) { exitHero(() => enterPresence()); return; }
  if (presenceOn || presenceBusy) return;
  entity.target = "full";
  presenceBusy = true;
  stageOut("");
  document.body.classList.add("presence");
  flyTo(1, 1100, () => {
    presenceOn = true; presenceBusy = false;
    document.body.classList.add("presence-ui");
  });
  entity.rippleT = 0;
  tickClock(); clockTimer = setInterval(tickClock, 10000);
  try { wakeLock = await navigator.wakeLock?.request("screen"); } catch {}
  try { await document.documentElement.requestFullscreen?.({ navigationUI: "hide" }); } catch {}
}

function exitPresence() {
  if (!presenceOn || presenceBusy) return;
  presenceBusy = true;
  document.body.classList.remove("presence-ui");
  clearInterval(clockTimer);
  try { wakeLock?.release(); } catch {}
  wakeLock = null;
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  setTimeout(() => {
    document.body.classList.remove("presence");
    entity.rippleT = 0;
    flyTo(0, 1000, () => {
      // La sphère est exactement au-dessus de sa place : on la range.
      stageBack();
      presenceOn = false; presenceBusy = false;
    });
  }, 220);
}
stageEl.addEventListener("click", (e) => {
  if (e.target.closest("button") || entity.wasLongPress()) return;
  if (presenceBusy) return;
  presenceOn ? exitPresence() : enterPresence();
});
$("presenceBtn").onclick = enterPresence;
document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement && presenceOn) exitPresence(); });

/* ============================================================
   APPLICATION INSTALLABLE (PWA)
   ============================================================ */
let installEvt = null;
if ("serviceWorker" in navigator && isSecureContext) navigator.serviceWorker.register("/sw.js").catch(() => {});
addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installEvt = e; $("installBtn").style.display = ""; });
$("installBtn").onclick = async () => { if (!installEvt) return; installEvt.prompt(); await installEvt.userChoice; installEvt = null; $("installBtn").style.display = "none"; };
(function installHint() {
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  $("installInfo").textContent = standalone ? "Atom est installé sur cet appareil."
    : !isSecureContext ? "L'installation demande une connexion HTTPS. Avec Tailscale (voir le README), ouvre Atom via son adresse https://…ts.net : le bouton d'installation apparaîtra ici."
    : /iphone|ipad/i.test(navigator.userAgent) ? "Sur iPhone : bouton Partager → « Sur l'écran d'accueil »."
    : "Utilise le bouton ci-dessous, ou le menu du navigateur → « Installer l'application ».";
})();

/* ============================================================
   RECHERCHE WEB (bouton globe + réglage)
   ============================================================ */
let webForce = false, searchAvailable = true;
function renderWebBtn() {
  const b = $("webBtn");
  b.classList.toggle("on", webForce);
  b.style.display = searchAvailable ? "" : "none";
  b.title = webForce ? "Recherche Internet activée pour ce message (clic pour annuler)"
    : settings.webAuto === false ? "Rechercher sur Internet pour ce message" : "Forcer une recherche Internet (sinon Atom décide)";
}
$("webBtn").onclick = () => { webForce = !webForce; renderWebBtn(); input.focus(); };
$("webAuto").checked = settings.webAuto !== false;
$("webAuto").onchange = () => { settings.webAuto = $("webAuto").checked; saveSettings(); renderWebBtn(); };

document.querySelectorAll(".side-nav [data-goto]").forEach((b) => { b.onclick = () => openSettings(b.dataset.goto); });
async function refreshCounts() {
  try { const m = (await getJSON("/api/memories")).memories.length; $("navMem").textContent = m || ""; } catch {}
  try { const r = (await getJSON("/api/reminders")).reminders.length; $("navRem").textContent = r || ""; } catch {}
}

/* ============================================================
   SAUVEGARDE ET VITESSE
   ============================================================ */
async function loadBackups() {
  let d;
  try { d = await getJSON("/api/backups"); } catch { return; }
  $("bkInfo").textContent = `Atom copie toute sa mémoire (conversations, souvenirs, rappels) chaque nuit à ${d.time}, et garde les ${d.keep} dernières copies dans le dossier « backups » du serveur.`;
  const label = { auto: "automatique", manual: "manuelle", export: "téléchargée", prerestore: "avant restauration", "": "" };
  $("bkList").innerHTML = d.backups.length ? "" : '<li class="none">Aucune sauvegarde pour l\'instant.</li>';
  for (const b of d.backups) {
    const li = document.createElement("li");
    li.style.cssText = "display:flex;align-items:center;gap:8px";
    li.innerHTML = `<div style="flex:1"><small>${esc(new Date(b.created_at * 1000).toLocaleString("fr-FR"))} · ${fmtBytes(b.size)}</small>${esc(label[b.tag] ?? b.tag)}</div>`;
    const dl = document.createElement("a");
    dl.className = "iconbtn"; dl.title = "Télécharger"; dl.href = `/api/backups/${encodeURIComponent(b.name)}/download`; dl.innerHTML = icon("download");
    const rs = document.createElement("button");
    rs.className = "btn"; rs.textContent = "Restaurer";
    rs.onclick = async () => {
      if (!confirm("Restaurer cette sauvegarde ? L'état actuel sera sauvegardé avant.")) return;
      try { await send_(`/api/backups/${encodeURIComponent(b.name)}/restore`, "POST"); toast("<b>Mémoire restaurée</b> · rechargement…"); setTimeout(() => location.reload(), 900); }
      catch (e) { toast(esc(e.message)); }
    };
    li.append(dl, rs);
    $("bkList").appendChild(li);
  }
}
$("bkNow").onclick = async () => { try { await send_("/api/backups", "POST"); entity.seal = 1; toast("<b>Sauvegarde créée</b>"); } catch (e) { toast(esc(e.message)); } loadBackups(); };
$("bkExport").onclick = () => { location.href = "/api/export"; setTimeout(loadBackups, 1500); };
$("bkImport").onclick = () => $("bkFile").click();
$("bkFile").onchange = async (e) => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f || !confirm(`Restaurer « ${f.name} » ? L'état actuel sera sauvegardé avant.`)) return;
  try {
    const r = await fetch("/api/import", { method: "POST", body: f, headers: { "Content-Type": "application/octet-stream", "X-Atom": "1" } });
    if (!r.ok) throw new Error((await r.json()).detail || "Échec");
    toast("<b>Mémoire restaurée</b> · rechargement…"); setTimeout(() => location.reload(), 900);
  } catch (err) { toast(esc(err.message)); }
};
$("benchBtn").onclick = async () => {
  $("benchInfo").textContent = "Mesure en cours (le modèle écrit une phrase)…";
  try {
    const r = await (await api("/api/benchmark", { method: "POST" })).json();
    const tips = r.tok_s == null ? "" : r.tok_s < 3 ? " · Lent : voir « Vitesse » dans le README." : r.tok_s < 7 ? " · Correct pour un CPU." : " · Bonne vitesse.";
    $("benchInfo").textContent = r.tok_s == null ? `Terminé en ${r.wall_s} s.`
      : `Écriture : ${r.tok_s} tok/s · lecture du contexte : ${r.prompt_tok_s ?? "—"} tok/s · chargement du modèle : ${r.load_s} s${tips}`;
    if (r.tok_s) $("speedV").textContent = r.tok_s.toFixed(1) + " tok/s";
  } catch (e) { $("benchInfo").textContent = e.message; }
};
