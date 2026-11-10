/* ============================================================
   AGENDA : page principale (semaine, ajout, modification) et lien d'abonnement (Réglages → Agenda)
   ============================================================ */
const AG_REP = { daily: "chaque jour", weekly: "chaque semaine", monthly: "chaque mois", yearly: "chaque année" };
let agWeek = null, agEdit = null;
const agIso = (d) => new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
function agMonday(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x; }
const agDate = (iso) => new Date(`${iso}T12:00:00`);   // midi : à l'abri des changements d'heure
function agDayLabel(d, todayIso) {
  const t = todayIso ? agDate(todayIso) : new Date(new Date().setHours(12, 0, 0, 0));
  const diff = Math.round((agDate(agIso(d)) - t) / 86400000);
  const base = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  return (diff === 0 ? "Aujourd'hui · " : diff === 1 ? "Demain · " : "") + base.replace(/^./, (c) => c.toUpperCase());
}

async function loadAgendaView() {
  agWeek = agWeek || agMonday(new Date());
  const end = new Date(agWeek); end.setDate(end.getDate() + 7);
  const last = new Date(end); last.setDate(last.getDate() - 1);
  $("agvRange").textContent = `${agWeek.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} – ${last.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })}`;
  let d; try { d = await getJSON(`/api/agenda?start=${agIso(agWeek)}&end=${agIso(end)}`); } catch { return; }
  // Jours et heures fournis par le serveur, dans le fuseau d'Atom : ce qu'on voit est ce qu'on enregistre.
  const box = $("agvDays"); box.innerHTML = "";
  const today = d.today || agIso(new Date());
  for (let i = 0; i < 7; i++) {
    const day = new Date(agWeek); day.setDate(day.getDate() + i);
    const iso = agIso(day), past = iso < today;
    const items = d.occurrences.filter((o) => o.day === iso);
    const col = document.createElement("section");
    col.className = "agv-day" + (iso === today ? " today" : "") + (past ? " past" : "");
    col.innerHTML = `<h3>${esc(agDayLabel(day, today))}</h3>`;
    if (!items.length) {
      const empty = document.createElement("button"); empty.className = "agv-empty"; empty.type = "button";
      empty.textContent = past ? "—" : "Libre · ajouter"; empty.disabled = past;
      empty.onclick = () => openAgSheet(null, day); col.appendChild(empty);
    }
    for (const o of items) {
      const b = document.createElement("button"); b.type = "button"; b.className = "agv-ev";
      b.innerHTML = `<span class="agv-t">${o.all_day ? "Journée" : `${o.start_hm}<small>${o.end_hm}</small>`}</span>
        <span class="agv-n"><b>${esc(o.title)}</b>${o.location ? `<small>📍 ${esc(o.location)}</small>` : ""}${o.repeat ? `<small>↻ ${AG_REP[o.repeat] || ""}</small>` : ""}</span>`;
      b.onclick = () => openAgSheet(o);
      col.appendChild(b);
    }
    box.appendChild(col);
  }
  const t = box.querySelector(".agv-day.today");
  if (t && narrow()) t.scrollIntoView({ block: "start" });
  if (typeof agvTip === "function") agvTip();   // conseil : activer les notifications
}

async function openAgSheet(occ, day) {
  agEdit = null;
  const s = $("agSheet");
  $("agsTitle").textContent = occ ? "Modifier le rendez-vous" : "Nouveau rendez-vous";
  $("agsSub").textContent = occ ? (occ.when || "") : "Ou dis-le simplement à Atom : « dentiste jeudi à 14 h ».";
  ["agsName", "agsLoc", "agsNotes", "agsTime"].forEach((id) => { $(id).value = ""; });
  $("agsRep").value = ""; $("agsRem").value = "30"; $("agsDur").value = "60";
  $("agsDate").value = agIso(day || new Date());
  $("agsDel").hidden = $("agsDelOne").hidden = $("agsSeries").hidden = true;
  if (occ) {
    let ev; try { ev = await getJSON(`/api/agenda/${occ.id}`); } catch (e) { toast(esc(e.message)); return; }
    agEdit = { ev, occ };
    $("agsName").value = ev.title; $("agsLoc").value = ev.location; $("agsNotes").value = ev.notes;
    $("agsDate").value = ev.start_date; $("agsTime").value = ev.all_day ? "" : ev.start_hm;
    const mins = ev.minutes;
    if (![...$("agsDur").options].some((o) => +o.value === mins)) $("agsDur").add(new Option(`${Math.floor(mins / 60)} h ${String(mins % 60).padStart(2, "0")}`, mins));
    $("agsDur").value = String(mins);
    $("agsRep").value = ev.repeat; $("agsRem").value = ev.remind_min == null ? "" : String(ev.remind_min);
    if (![...$("agsRem").options].some((o) => o.value === $("agsRem").value)) $("agsRem").add(new Option(`${ev.remind_min} min avant`, ev.remind_min));
    $("agsDel").hidden = false; $("agsDel").textContent = ev.repeat ? "Supprimer la série" : "Supprimer";
    $("agsDelOne").hidden = !ev.repeat; $("agsSeries").hidden = !ev.repeat;
  }
  s.hidden = false;
  setTimeout(() => $("agsName").focus(), 30);
}
const closeAgSheet = () => { $("agSheet").hidden = true; agEdit = null; };
$("agsClose").onclick = closeAgSheet;
$("agSheet").addEventListener("keydown", (e) => { if (e.key === "Escape") closeAgSheet(); });
$("agSheet").addEventListener("mousedown", (e) => { if (e.target === $("agSheet")) closeAgSheet(); });
$("agsSave").onclick = async () => {
  const title = $("agsName").value.trim(), date = $("agsDate").value, time = $("agsTime").value;
  if (!title || !date) { toast("Indique au moins un titre et une date."); return; }
  const body = { title, start: time ? `${date}T${time}` : date, minutes: +$("agsDur").value, location: $("agsLoc").value.trim(),
    notes: $("agsNotes").value.trim(), repeat: $("agsRep").value, remind_min: $("agsRem").value === "" ? null : +$("agsRem").value };
  try {
    if (agEdit) await send_(`/api/agenda/${agEdit.ev.id}`, "PUT", body);
    else await send_("/api/agenda", "POST", body);
    toast(`<b>📅 ${agEdit ? "Modifié" : "Ajouté"}</b> · ${esc(title)}`);
    closeAgSheet(); loadAgendaView();
  } catch (e) { toast(esc(e.message)); }
};
async function agDelete(url, ask) {
  if (!confirm(ask)) return;
  try { await send_(url, "DELETE"); toast("Supprimé."); closeAgSheet(); loadAgendaView(); } catch (e) { toast(esc(e.message)); }
}
$("agsDel").onclick = () => agEdit && agDelete(`/api/agenda/${agEdit.ev.id}`,
  agEdit.ev.repeat ? `Supprimer toute la série « ${agEdit.ev.title} » ?` : `Supprimer « ${agEdit.ev.title} » ?`);
$("agsDelOne").onclick = () => agEdit && agDelete(`/api/agenda/${agEdit.ev.id}?occurrence=${agEdit.occ.start}`,
  `Supprimer « ${agEdit.ev.title} » de ce jour seulement ?`);

$("agvPrev").onclick = () => { agWeek.setDate(agWeek.getDate() - 7); loadAgendaView(); };
$("agvNext").onclick = () => { agWeek.setDate(agWeek.getDate() + 7); loadAgendaView(); };
$("agvToday").onclick = () => { agWeek = agMonday(new Date()); loadAgendaView(); };
$("agvAdd").onclick = $("agvFab").onclick = () => openAgSheet(null, new Date());
$("navAgenda").onclick = () => showView(currentView === "agenda" ? "chat" : "agenda");
$("agOpenView").onclick = () => { closeSettings(); showView("agenda"); };

// Réglages → Agenda : lien d'abonnement facultatif (Google Agenda via ICSx⁵)
async function loadAgenda() {
  try { const f = await getJSON("/api/agenda/feed"); $("agFeed").value = f.url; } catch {}
  if (currentView === "agenda") loadAgendaView();
}
$("agFeedCopy").onclick = () => { copyText($("agFeed").value); toast("Lien copié."); };
$("agFeedNew").onclick = async () => {
  if (!confirm("Créer un nouveau lien ? L'ancien cessera de fonctionner.")) return;
  try { const f = await send_("/api/agenda/feed/regenerate", "POST").then((r) => r.json()); $("agFeed").value = f.url; toast("Nouveau lien créé."); }
  catch (e) { toast(esc(e.message)); }
};
