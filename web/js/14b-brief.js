/* ============================================================
   BRIEF DU MATIN (Réglages → Données)
   ============================================================ */
const BR_DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
let brCfg = null;
async function loadBrief() {
  try { brCfg = await getJSON("/api/brief"); } catch { return; }
  const c = brCfg;
  $("brEnabled").checked = c.enabled; $("brTime").value = c.time; $("brCity").value = c.city; $("brNews").value = c.news;
  $("brIntro").checked = c.intro;
  $("brDays").innerHTML = BR_DAYS.map((d, i) => `<button type="button" class="btn${c.days.includes(i) ? " primary" : ""}" data-d="${i}" aria-pressed="${c.days.includes(i)}">${d}</button>`).join("");
  $("brDays").querySelectorAll("[data-d]").forEach((b) => b.onclick = () => {
    const d = +b.dataset.d, days = brCfg.days.includes(d) ? brCfg.days.filter((x) => x !== d) : [...brCfg.days, d];
    brSave({ days });
  });
  $("brSections").innerHTML = Object.entries(c.names).map(([k, n]) =>
    `<label class="switch"><span>${esc(n)}</span><input type="checkbox" data-sec="${k}"${c.sections[k] ? " checked" : ""}></label>`).join("");
  $("brSections").querySelectorAll("[data-sec]").forEach((x) => x.onchange = () => brSave({ sections: { [x.dataset.sec]: x.checked } }));
  const last = c.last && c.last.at ? `Dernier envoi : ${new Date(c.last.at * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}${c.last.sent ? "" : " (aucun canal n'a pu l'envoyer)"}. ` : "";
  $("brInfo").textContent = last + (c.channels ? "" : "Aucun canal configuré (Telegram ou ntfy) : le brief sera seulement rangé dans sa conversation.");
}
async function brSave(patch) {
  try { brCfg = await send_("/api/brief", "PUT", patch).then((r) => r.json()); loadBrief(); toast("Brief enregistré."); }
  catch (e) { toast(esc(e.message)); }
}
$("brEnabled").onchange = () => brSave({ enabled: $("brEnabled").checked });
$("brTime").onchange = () => $("brTime").value && brSave({ time: $("brTime").value });
$("brCity").onchange = () => brSave({ city: $("brCity").value });
$("brNews").onchange = () => brSave({ news: $("brNews").value });
$("brIntro").onchange = () => brSave({ intro: $("brIntro").checked });
async function brRun(url, btn, label) {
  btn.disabled = true; const t = btn.textContent; btn.textContent = label;
  try {
    const b = await send_(url, "POST", {}).then((r) => r.json());
    $("brOut").hidden = false; setMd($("brOut"), `**${b.title}**\n\n${b.text}`);
    if (url.endsWith("send")) { toast(b.sent ? "Brief envoyé." : "Brief rangé dans sa conversation (aucun canal n'a pu l'envoyer)."); loadBrief(); loadConversations(); }
  } catch (e) { toast(esc(e.message)); }
  btn.disabled = false; btn.textContent = t;
}
$("brPreview").onclick = () => brRun("/api/brief/preview", $("brPreview"), "Préparation…");
$("brSend").onclick = () => brRun("/api/brief/send", $("brSend"), "Envoi…");
