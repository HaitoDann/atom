"use strict";

/* ============================================================
   PANNEAU : système, rappels, souvenirs
   ============================================================ */
async function refreshSystem() {
  if (!panelVisible()) return;
  try {
    const s = await getJSON("/api/system");
    if (s.cpu != null) entity.load = Math.max(0, Math.min(1, (s.cpu - 10) / 80));
    if (s.cpu != null) { $("cpuV").textContent = `${Math.round(s.cpu)} %${s.cores ? ` · ${s.cores} cœurs` : ""}`; $("cpuB").style.width = Math.min(100, s.cpu) + "%"; }
    if (s.memory) { $("ramV").textContent = `${fmtBytes(s.memory.used)} / ${fmtBytes(s.memory.total)}`; $("ramB").style.width = (100 * s.memory.used / s.memory.total) + "%"; }
    $("loadedV").textContent = s.loaded.length ? s.loaded.map((m) => m.name.split(":")[0] + (m.size ? ` · ${fmtBytes(m.size)}` : "")).join(", ") : "aucun (en veille)";
    $("upV").textContent = fmtDur(s.uptime);
  } catch {}
}

// Ligne « aujourd'hui » de l'accueil : rappels du jour, état du serveur, mémoire
async function renderToday() {
  const box = $("today"); if (!box) return;
  const parts = [];
  try {
    const r = (await getJSON("/api/reminders")).reminders;
    const end = new Date(); end.setHours(23, 59, 59, 999);
    const today = r.filter((x) => x.due_at * 1000 <= end.getTime());
    parts.push(`<button data-go="reminders"><span class="dot${today.length ? " warn" : ""}"></span>${today.length ? `${today.length} rappel${today.length > 1 ? "s" : ""} aujourd'hui` : "aucun rappel aujourd'hui"}</button>`);
  } catch {}
  try {
    const p = await getJSON("/api/proxmox");
    if (p.configured) {
      const n = p.alerts?.length || 0, run = p.guests.filter((g) => g.status === "running").length;
      parts.push(`<button data-go="proxmox"><span class="dot ${!p.ok ? "err" : n ? "warn" : "ok"}"></span>${!p.ok ? "serveur injoignable" : n ? `${n} alerte${n > 1 ? "s" : ""} serveur` : `serveur OK · ${run} en marche`}</button>`);
    }
  } catch {}
  try {
    const m = (await getJSON("/api/memories")).memories.length;
    if (m) parts.push(`<button data-go="memory"><span class="dot"></span>${m} souvenir${m > 1 ? "s" : ""}</button>`);
  } catch {}
  if (!$("today")) return;
  box.innerHTML = parts.join("");
  box.querySelectorAll("[data-go]").forEach((b) => { b.onclick = () => openSettings(b.dataset.go); });
}
async function refreshPanel() {
  if (!panelVisible()) return;
  try {   // serveur Proxmox (si configuré)
    const p = await getJSON("/api/proxmox");
    $("pxSec").hidden = !p.configured;
    if (p.configured) {
      const n = p.nodes[0], run = p.guests.filter((g) => g.status === "running").length;
      $("pxMini").innerHTML = !p.ok ? `<p class="alert">Injoignable : ${esc(p.error)}</p>` : `<div class="px-mini">
        ${(p.alerts || []).map((a) => `<p class="alert">⚠ ${esc(a.title)}</p>`).join("")}
        ${n ? `<div class="metric"><div class="l"><span>${esc(n.name)} · processeur</span><span>${n.cpu.toFixed(0)} %</span></div><div class="bar"><i style="width:${n.cpu}%"></i></div></div>
        <div class="metric"><div class="l"><span>Mémoire</span><span>${n.mem.toFixed(0)} %</span></div><div class="bar"><i style="width:${n.mem}%"></i></div></div>` : ""}
        <div class="kv"><span>Invités en marche</span><span>${run} / ${p.guests.length}</span></div></div>`;
      $("pxMini").onclick = () => openSettings("proxmox");
    }
  } catch { $("pxSec").hidden = true; }
  try {
    const r = (await getJSON("/api/reminders")).reminders.slice(0, 3);
    $("pRem").innerHTML = r.length
      ? r.map((x) => `<li><small>${esc(x.when)}</small>${esc(x.text)}</li>`).join("")
      : '<li class="none">Aucun rappel programmé.</li>';
  } catch {}
  try {
    const m = (await getJSON("/api/memories")).memories.slice(-4).reverse();
    $("pMem").innerHTML = m.length
      ? m.map((x) => `<li>${esc(x.content)}</li>`).join("")
      : '<li class="none">Rien de retenu pour l\'instant.</li>';
  } catch {}
}
document.querySelectorAll("[data-goto]").forEach((b) => { b.onclick = () => openSettings(b.dataset.goto); });

/* ============================================================
   RÉGLAGES
   ============================================================ */
// Cinq groupes ; chaque ancien panneau devient une section de son groupe.
const SET_GROUPS = {
  atom: ["general", "look", "entity"],
  discussion: ["workshop"],
  data: ["memory", "reminders", "brief", "backup"],
  connections: ["hybrid"],
  system: ["status", "proxmox", "lab", "security"],
};
const PANE_TITLES = { general: "Général", look: "Apparence", entity: "Entité", workshop: "Atelier multi-IA", memory: "Souvenirs",
  reminders: "Rappels", brief: "Brief du matin", backup: "Sauvegarde", hybrid: "Mode hybride", status: "État", proxmox: "Serveur Proxmox", lab: "Modèles locaux", security: "Sécurité" };
const PANE_LOAD = { memory: () => loadMemories(), reminders: () => loadReminders(), backup: () => { loadBackups(); loadOffsite(); }, status: () => loadStatus(),
  security: () => loadSecurity(), hybrid: () => loadHybrid(), workshop: () => loadWorkshop(), lab: () => loadLab(), proxmox: () => loadProxmox(), brief: () => loadBrief() };
const setGroupOf = (pane) => Object.keys(SET_GROUPS).find((g) => SET_GROUPS[g].includes(pane)) || pane;
document.querySelectorAll(".pane").forEach((p) => {
  const h = document.createElement("h3"); h.className = "pane-title"; h.textContent = PANE_TITLES[p.dataset.pane] || ""; p.prepend(h);
});
function openSettings(tab = "atom") {
  $("settings").classList.add("open");
  selectTab(tab);
}
function closeSettings() { $("settings").classList.remove("open"); }
function selectTab(tab) {
  const g = setGroupOf(tab), panes = SET_GROUPS[g] || [];
  $("setSearch").value = ""; filterSettings("");
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.tab === g));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", panes.includes(p.dataset.pane)));
  panes.forEach((p) => PANE_LOAD[p] && PANE_LOAD[p]());
  const target = document.querySelector(`.pane[data-pane="${tab}"]`);
  if (target && tab !== panes[0]) requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
  else document.querySelector(".pane-wrap").scrollTop = 0;
}
// Recherche : affiche, tous groupes confondus, les blocs dont le texte correspond.
const norm = (x) => x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
function filterSettings(q) {
  q = norm(q.trim());
  $("settings").classList.toggle("searching", !!q);
  if (!q) { document.querySelectorAll(".pane .block").forEach((b) => (b.hidden = false)); return; }
  let any = false;
  document.querySelectorAll(".pane").forEach((p) => {
    let hit = false;
    p.querySelectorAll(".block").forEach((b) => { const m = norm(b.textContent).includes(q); b.hidden = !m; hit = hit || m; });
    p.classList.toggle("on", hit); any = any || hit;
    if (hit && PANE_LOAD[p.dataset.pane]) PANE_LOAD[p.dataset.pane]();
  });
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("on"));
  $("setEmpty").hidden = any;
}
$("setSearch").oninput = () => filterSettings($("setSearch").value);
document.querySelectorAll(".tab").forEach((t) => { t.onclick = () => selectTab(t.dataset.tab); });
$("openSettings").onclick = () => openSettings();
$("closeSettings").onclick = closeSettings;
$("settings").addEventListener("click", (e) => { if (e.target.id === "settings") closeSettings(); });

$("persona").value = settings.persona;
$("persona").oninput = () => { settings.persona = $("persona").value; saveSettings(); };
$("autoMem").checked = settings.autoMemory;
$("autoMem").onchange = () => { settings.autoMemory = $("autoMem").checked; saveSettings(); };
$("reconnect").onclick = () => connect(true);

let memories = [];
let memArchived = false, memArchCount = 0;
const MEM_KIND = { semantique: "fait", procedurale: "habitude", episodique: "événement" };
async function loadMemories() {
  try { const d = await getJSON(`/api/memories${memArchived ? "?archived=1" : ""}`); memories = d.memories; memArchCount = d.archived || 0; } catch (e) { console.warn(e); }
  const box = $("memList");
  box.innerHTML = "";
  memories.sort((a, b) => (b.to_review - a.to_review) || ((b.importance || 2) - (a.importance || 2)) || (b.updated_at - a.updated_at));
  for (const m of memories) {
    const row = document.createElement("div");
    row.className = "mem" + (m.to_review ? " review" : "") + (m.archived_at ? " archived" : "");
    const tag = document.createElement("button");
    tag.type = "button"; tag.className = "tag";
    tag.textContent = (MEM_KIND[m.kind] || "fait") + ((m.importance || 2) >= 3 ? " ★" : "");
    tag.title = `${m.source === "auto" ? "Retenu automatiquement" : "Ajouté par toi"} · confiance ${Math.round((m.confidence || 0.8) * 100)} % · utilisé ${m.hits || 0} fois\nClic : changer le type · Maj+clic : essentiel oui/non`;
    tag.onclick = async (e) => {
      const body = e.shiftKey ? { importance: (m.importance || 2) >= 3 ? 2 : 3 } : { kind: { semantique: "procedurale", procedurale: "episodique", episodique: "semantique" }[m.kind || "semantique"] };
      try { await send_(`/api/memories/${m.id}/meta`, "POST", body); } catch {} loadMemories();
    };
    const inp = document.createElement("input");
    inp.value = m.content;
    const del = document.createElement("button");
    del.className = "iconbtn"; del.title = "Oublier"; del.innerHTML = icon("trash");
    del.onclick = async () => { try { await send_(`/api/memories/${m.id}`, "DELETE"); } catch {} loadMemories(); refreshPanel(); };
    inp.onchange = async () => {
      const v = inp.value.trim();
      if (!v) return del.onclick();
      try { await send_(`/api/memories/${m.id}`, "PATCH", { content: v }); m.content = v; refreshPanel(); }
      catch (e) { toast(esc(e.message)); inp.value = m.content; }
    };
    row.append(tag, inp);
    if (m.to_review) {   // fait temporaire arrivé à échéance
      const keep = document.createElement("button"); keep.className = "btn sm"; keep.textContent = "Toujours vrai";
      keep.onclick = async () => { await send_(`/api/memories/${m.id}/meta`, "POST", { confirm: true }); loadMemories(); };
      row.append(keep);
    }
    if (m.archived_at) {
      const back = document.createElement("button"); back.className = "btn sm"; back.textContent = "Restaurer";
      back.title = "Ce souvenir a été remplacé par une information plus récente (ou une contradiction).";
      back.onclick = async () => { await send_(`/api/memories/${m.id}/meta`, "POST", { restore: true }); loadMemories(); };
      row.append(back);
    }
    row.append(del);
    box.appendChild(row);
  }
  const rev = memories.filter((m) => m.to_review).length;
  $("memArchToggle").textContent = memArchived ? "← Souvenirs actifs" : memArchCount ? `Historique (${memArchCount} remplacé${memArchCount > 1 ? "s" : ""})` : "";
  $("memArchToggle").hidden = !memArchived && !memArchCount;
  if (rev && !memArchived) $("memInfo").textContent = `${rev} souvenir${rev > 1 ? "s" : ""} temporaire${rev > 1 ? "s" : ""} à revoir : confirme-les ou oublie-les. Atom ne s'en sert plus en attendant.`;
  else $("memInfo").textContent = memArchived ? "Souvenirs remplacés par une information plus récente (contradiction ou mise à jour)." : memories.length
    ? `${memories.length} souvenir(s). Atom retient seul les informations durables ; modifie ou supprime ce qui ne te convient pas.`
    : "Atom n'a encore rien retenu. Il apprendra au fil des conversations.";
}
$("memArchToggle").onclick = () => { memArchived = !memArchived; loadMemories(); };
$("memAdd").onclick = async () => {
  const v = $("memNew").value.trim();
  if (!v) return;
  try {
    const r = await (await send_("/api/memories", "POST", { content: v })).json(); $("memNew").value = "";
    if (r.action === "replaced") toast(`Souvenir mis à jour · remplace « ${esc(r.replaced)} » (gardé dans l'historique)`);
    else if (r.action === "merged") toast(`Fusionné avec un souvenir existant : « ${esc(r.content)} »`);
  } catch (e) { toast(esc(e.message)); }
  loadMemories(); refreshPanel();
};
$("memNew").onkeydown = (e) => { if (e.key === "Enter") $("memAdd").onclick(); };
$("clearMem").onclick = async () => {
  if (!confirm("Effacer tout ce qu'Atom sait de toi ?")) return;
  try { await send_("/api/memories", "DELETE"); } catch {}
  loadMemories(); refreshPanel();
};

async function loadReminders() {
  let data = { reminders: [], notifications: false };
  try { data = await getJSON("/api/reminders"); } catch {}
  const ul = $("remList");
  ul.innerHTML = data.reminders.length ? "" : '<li class="none">Aucun rappel programmé.</li>';
  for (const r of data.reminders) {
    const li = document.createElement("li");
    li.style.display = "flex"; li.style.alignItems = "center"; li.style.gap = "10px";
    li.innerHTML = `<div style="flex:1"><small>${esc(r.when)}</small>${esc(r.text)}</div>`;
    const del = document.createElement("button");
    del.className = "iconbtn"; del.title = "Annuler"; del.innerHTML = icon("trash");
    del.onclick = async () => { try { await send_(`/api/reminders/${r.id}`, "DELETE"); } catch {} loadReminders(); refreshPanel(); };
    li.appendChild(del);
    ul.appendChild(li);
  }
  $("remInfo").textContent = data.notifications ? "" : "Aucun canal de notification configuré (ntfy ou Telegram) : les rappels n'apparaîtront que dans la conversation.";
}
$("notifTest").onclick = async () => {
  try { await send_("/api/notify/test", "POST"); toast("<b>Notification envoyée</b> · regarde ton téléphone."); }
  catch (e) { toast(esc(e.message)); }
};

for (const e of EMOTIONS) {
  const b = document.createElement("button");
  b.className = "chip"; b.textContent = ACTIVITIES[e].label;
  b.onclick = () => setEmotion(e);
  $("emos").appendChild(b);
}
const DEMOS = [
  ["Travail long · recherche web", () => { entity.feedColor = [110, 170, 255]; entity.feeding = true; setTimeout(() => { entity.feeding = false; }, 4000); }],
  ["Travail long · documents", () => { entity.scan = true; setTimeout(() => { entity.scan = false; }, 4000); }],
  ["Travail long · IA distante", () => { entity.remote = true; setTimeout(() => { entity.remote = false; }, 4000); }],
  ["Travail long · atelier / agent", () => { entity.split = 2; setTimeout(() => { entity.split = 0; }, 4000); }],
];
const demoRow = document.createElement("div");
demoRow.className = "emos"; demoRow.style.marginTop = "12px";
for (const [label, fn] of DEMOS) { const b = document.createElement("button"); b.className = "chip"; b.textContent = label; b.onclick = fn; demoRow.appendChild(b); }
$("emos").after(demoRow);
