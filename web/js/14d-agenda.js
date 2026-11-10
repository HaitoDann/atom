/* ============================================================
   AGENDA (Réglages → Données → Agenda)
   ============================================================ */
const AG_REP = { daily: "chaque jour", weekly: "chaque semaine", monthly: "chaque mois", yearly: "chaque année" };
function agDayLabel(ts) {
  const d = new Date(ts * 1000), t = new Date(); t.setHours(0, 0, 0, 0);
  const diff = Math.round((new Date(d).setHours(0, 0, 0, 0) - t) / 86400000);
  if (diff === 0) return "Aujourd'hui";
  if (diff === 1) return "Demain";
  return d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }).replace(/^./, (c) => c.toUpperCase());
}
const agHour = (ts) => new Date(ts * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
async function loadAgenda() {
  let d; try { d = await getJSON("/api/agenda?days=60"); } catch { return; }
  const box = $("agList"); box.innerHTML = "";
  if (!d.occurrences.length) box.innerHTML = '<p class="note">Rien de prévu ces 60 prochains jours.</p>';
  let day = "";
  for (const o of d.occurrences) {
    const lab = agDayLabel(o.start);
    if (lab !== day) { day = lab; const h = document.createElement("div"); h.className = "ag-day"; h.textContent = lab; box.appendChild(h); }
    const row = document.createElement("div"); row.className = "ag-ev";
    row.innerHTML = `<span class="ag-t">${o.all_day ? "journée" : `${agHour(o.start)}–${agHour(o.end)}`}</span>
      <span class="ag-n"><b>${esc(o.title)}</b>${o.location ? `<small>📍 ${esc(o.location)}</small>` : ""}${o.repeat ? `<small>↻ ${AG_REP[o.repeat] || ""}</small>` : ""}</span>`;
    const mk = (title, url, ask) => {
      const del = document.createElement("button"); del.className = "iconbtn"; del.title = title; del.setAttribute("aria-label", title); del.innerHTML = icon("trash");
      del.onclick = async () => {
        if (!confirm(ask)) return;
        try { await send_(url, "DELETE"); toast("Supprimé."); } catch (e) { toast(esc(e.message)); }
        loadAgenda();
      };
      return del;
    };
    if (o.repeat) {
      row.appendChild(mk("Supprimer cette occurrence", `/api/agenda/${o.id}?occurrence=${o.start}`, `Supprimer « ${o.title} » du ${agDayLabel(o.start).toLowerCase()} seulement ?`));
      const series = mk("Supprimer toute la série", `/api/agenda/${o.id}`, `Supprimer toute la série « ${o.title} » (${AG_REP[o.repeat]}) ?`);
      series.innerHTML = "série"; series.className = "btn sm"; row.appendChild(series);
    } else row.appendChild(mk("Supprimer", `/api/agenda/${o.id}`, `Supprimer « ${o.title} » ?`));
    box.appendChild(row);
  }
  if (!$("agDate").value) $("agDate").value = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  try { const f = await getJSON("/api/agenda/feed"); $("agFeed").value = f.url; } catch {}
}
$("agAdd").onclick = async () => {
  const title = $("agTitle").value.trim(), date = $("agDate").value, time = $("agTime").value;
  if (!title || !date) { toast("Indique au moins un titre et une date."); return; }
  const body = { title, start: time ? `${date}T${time}` : date, minutes: +$("agDur").value, location: $("agLoc").value.trim(),
    repeat: $("agRep").value, remind_min: $("agRem").value === "" ? null : +$("agRem").value };
  try {
    await send_("/api/agenda", "POST", body);
    toast(`<b>📅 Ajouté</b> · ${esc(title)}`);
    $("agTitle").value = ""; $("agLoc").value = ""; $("agTime").value = ""; $("agRep").value = "";
    loadAgenda();
  } catch (e) { toast(esc(e.message)); }
};
$("agFeedCopy").onclick = () => { copyText($("agFeed").value); toast("Lien copié. Colle-le dans ICSx⁵ sur ton téléphone."); };
$("agFeedNew").onclick = async () => {
  if (!confirm("Créer un nouveau lien ? L'ancien cessera de fonctionner : il faudra mettre à jour ton téléphone.")) return;
  try { const f = await send_("/api/agenda/feed/regenerate", "POST").then((r) => r.json()); $("agFeed").value = f.url; toast("Nouveau lien créé."); }
  catch (e) { toast(esc(e.message)); }
};
