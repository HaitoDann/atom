"use strict";

/* ============================================================
   LABO DES MODÈLES LOCAUX — installer, comparer, choisir
   ============================================================ */
let lab = null, labTimer = 0, labRunning = false;
const gb = (b) => (b / 1e9).toFixed(1).replace(".", ",") + " Go";
async function loadLab() {
  try { lab = await getJSON("/api/lab"); } catch (e) { $("labMem").textContent = e.message; return; }
  const mem = lab.memory;
  const free = mem ? (mem.total - mem.used) : null;
  $("labMem").textContent = mem ? `Mémoire du serveur : ${gb(mem.used)} utilisés sur ${gb(mem.total)} · ${gb(free)} disponibles. Modèle actif : ${lab.current}.` : `Modèle actif : ${lab.current}.`;
  const cur = settings.model || lab.current;
  $("labInstalled").innerHTML = lab.installed.map((n) => `<div class="lab-item"><div class="n"><b>${esc(n)}</b>${n === cur ? "<small>utilisé par Atom</small>" : ""}</div>
    ${n === cur ? "" : `<button class="btn sm" data-use="${esc(n)}">Utiliser</button><button class="btn sm" data-del="${esc(n)}" title="Supprimer du serveur (libère l'espace disque)">Supprimer</button>`}</div>`).join("") || '<p class="note">Aucun modèle.</p>';
  const pull = (n) => lab.pulls.find((p) => p.name === n);
  $("labSuggested").innerHTML = lab.suggested.filter((m) => !lab.installed.includes(m.name)).map((m) => {
    const p = pull(m.name), busy = p && !p.done;
    const tight = free != null && m.size_gb * 1e9 > free;
    return `<div class="lab-item"><div class="n"><b>${esc(m.name)}</b><small>${esc(m.note)}</small>
      ${busy ? `<span class="idxbar"><i style="width:${p.total ? Math.round(100 * p.completed / p.total) : 2}%"></i></span><small>${esc(p.status)}${p.total ? ` · ${gb(p.completed)} / ${gb(p.total)}` : ""}</small>` : ""}
      ${p && p.error ? `<small style="color:var(--danger,#e66)">${esc(p.error)}</small>` : ""}
      ${tight && !busy ? `<small>⚠ ${m.size_gb} Go : plus que la mémoire disponible actuellement — ferme d'autres services ou il sera très lent.</small>` : ""}</div>
      <span class="tag">${m.size_gb} Go</span>${busy ? "" : `<button class="btn sm" data-inst="${esc(m.name)}">Installer</button>`}</div>`;
  }).join("") || '<p class="note">Tous les modèles suggérés sont installés.</p>';
  // installations hors suggestions
  for (const p of lab.pulls.filter((p) => !lab.suggested.some((m) => m.name === p.name) && !p.done))
    $("labSuggested").insertAdjacentHTML("beforeend", `<div class="lab-item"><div class="n"><b>${esc(p.name)}</b><span class="idxbar"><i style="width:${p.total ? Math.round(100 * p.completed / p.total) : 2}%"></i></span><small>${esc(p.status)}</small></div></div>`);
  document.querySelectorAll("#labSuggested [data-inst]").forEach((b) => { b.onclick = () => labInstall(b.dataset.inst); });
  document.querySelectorAll("#labInstalled [data-use]").forEach((b) => { b.onclick = () => labUse(b.dataset.use); });
  document.querySelectorAll("#labInstalled [data-del]").forEach((b) => {
    b.onclick = async () => {
      if (!confirm(`Supprimer ${b.dataset.del} du serveur ?`)) return;
      try { await send_("/api/lab/delete", "POST", { name: b.dataset.del }); toast(`${esc(b.dataset.del)} supprimé.`); connect(); } catch (e) { toast(esc(e.message)); }
      loadLab();
    };
  });
  // choix pour le comparatif (on garde les cases déjà cochées)
  const was = new Set([...document.querySelectorAll("#labPick input:checked")].map((i) => i.value));
  if (!was.size) { was.add(cur); const other = lab.installed.find((n) => n !== cur); if (other) was.add(other); }
  $("labPick").innerHTML = lab.installed.map((n) => `<label class="mono"><input type="checkbox" value="${esc(n)}" ${was.has(n) ? "checked" : ""}>${esc(n)}</label>`).join("")
    + lab.remote.map((r) => `<label class="mono" title="${esc(r.model)} · ${r.left} requêtes restantes aujourd'hui"><input type="checkbox" value="${esc(r.id)}" ${was.has(r.id) ? "checked" : ""}>${esc(r.name)} · ${esc(r.model.split("/").pop())}</label>`).join("");
  $("labRemoteNote").hidden = !lab.remote.length;
  if (!$("labPrompts").children.length)
    $("labPrompts").innerHTML = lab.prompts.map((p, i) => `<label><input type="checkbox" value="${p.id}" ${i < 3 ? "checked" : ""}>${esc(p.label)}</label>`).join("");
  clearTimeout(labTimer);
  if (lab.pulls.some((p) => !p.done) && $("settings").classList.contains("open")) labTimer = setTimeout(async () => {
    const before = lab.pulls.filter((p) => !p.done).map((p) => p.name);
    await loadLab();
    for (const n of before) { const p = lab.pulls.find((x) => x.name === n); if (p?.done) { toast(p.error ? `<b>${esc(n)}</b> · ${esc(p.error)}` : `<b>${esc(n)}</b> installé.`); if (!p.error) connect(); } }
  }, 1500);
}
async function labInstall(name) {
  name = name.trim(); if (!name) return;
  try { await send_("/api/lab/install", "POST", { name }); toast(`Installation de <b>${esc(name)}</b> lancée…`); } catch (e) { toast(esc(e.message)); }
  loadLab();
}
function labUse(name) {
  if (![...modelSel.options].some((o) => o.value === name)) modelSel.add(new Option(name, name));
  modelSel.value = name; modelSel.onchange(); loadLab();
}
const labName = (m) => { const r = lab?.remote.find((x) => x.id === m); return r ? `${r.name} · ${r.model}` : m; };
$("labInstall").onclick = () => { labInstall($("labName").value); $("labName").value = ""; };
$("labRun").onclick = async () => {
  if (labRunning) return;
  const models = [...document.querySelectorAll("#labPick input:checked")].map((i) => i.value).slice(0, 4);
  const prompts = [...document.querySelectorAll("#labPrompts input:checked")].map((i) => i.value);
  const custom = $("labCustom").value.trim();
  if (!models.length) { toast("Coche au moins un modèle (4 au plus)."); return; }
  if (!prompts.length && !custom) { toast("Coche au moins une question."); return; }
  const qs = [...lab.prompts.filter((p) => prompts.includes(p.id)), ...(custom ? [{ id: "perso", label: "Ta question" }] : [])];
  const box = $("labResults");
  box.innerHTML = `<div class="lab-res"><table><thead><tr><td class="q"></td>${models.map((m) => `<th>${esc(labName(m))}</th>`).join("")}</tr></thead><tbody>
    ${qs.map((q) => `<tr><td class="q">${esc(q.label)}</td>${models.map((m) => `<td data-c="${esc(m)}|${q.id}"><div class="m">en attente</div><div class="md"></div></td>`).join("")}</tr>`).join("")}
    <tr class="sum"><td class="q">Moyenne</td>${models.map((m) => `<td data-s="${esc(m)}">—</td>`).join("")}</tr>
    <tr><td class="q"></td>${models.map((m) => m.startsWith("p:") ? `<td><button class="btn sm" data-prov="${esc(m.slice(2))}">En faire le principal</button></td>` : `<td><button class="btn sm" data-pick="${esc(m)}">Utiliser ce modèle</button></td>`).join("")}</tr></tbody></table></div>`;
  box.querySelectorAll("[data-pick]").forEach((b) => { b.onclick = () => labUse(b.dataset.pick); });
  box.querySelectorAll("[data-prov]").forEach((b) => { b.onclick = async () => { await saveHybrid({ provider: b.dataset.prov }); toast(`Fournisseur principal : <b>${esc(labName("p:" + b.dataset.prov))}</b>`); }; });
  const cell = (m, q) => box.querySelector(`[data-c="${CSS.escape(m + "|" + q)}"]`);
  const agg = {};
  labRunning = true; $("labRun").disabled = true; $("labRunInfo").textContent = "Comparatif en cours…"; setEmotion("focus");
  const t0 = Date.now(), texts = {};
  try {
    const r = await api("/api/lab/compare", { method: "POST", body: JSON.stringify({ models, prompts, custom }) });
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "", q = false;
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true }); let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue;
        const ev = JSON.parse(line), c = ev.model ? cell(ev.model, ev.prompt) : null;
        if (ev.type === "start" && c) { c.querySelector(".m").innerHTML = '<span class="spin"></span> écrit…'; texts[ev.model + ev.prompt] = ""; $("labRunInfo").textContent = `${labName(ev.model)}…`; }
        else if (ev.type === "token" && c) {
          texts[ev.model + ev.prompt] += ev.text; entity.tokenKick = 1;
          if (!q) { q = true; requestAnimationFrame(() => { q = false; box.querySelectorAll("[data-c]").forEach((x) => { const k = x.dataset.c.replace("|", ""); if (texts[k] != null) x.querySelector(".md").innerHTML = md(texts[k].replace(/^\s*\[[a-z_]+\]\s*/i, "")); }); }); }
        } else if (ev.type === "result" && c) {
          c.querySelector(".m").textContent = `${ev.tok_s ?? "—"} tok/s · 1er mot ${ev.first_s} s · total ${ev.wall_s} s` + (ev.load_s > 1 ? ` · chargement ${ev.load_s} s` : "");
          delete texts[ev.model + ev.prompt];   // plus de rafraîchissement en flux : il effacerait les formules rendues
          setMd(c.querySelector(".md"), ev.text.replace(/^\s*\[[a-z_]+\]\s*/i, ""));
          (agg[ev.model] ||= []).push(ev);
          const a = agg[ev.model], avg = (k) => (a.reduce((s, x) => s + (x[k] || 0), 0) / a.length).toFixed(1).replace(".", ",");
          box.querySelector(`[data-s="${CSS.escape(ev.model)}"]`).textContent = `${avg("tok_s")} tok/s · 1er mot ${avg("first_s")} s`;
        } else if (ev.type === "error" && c) {
          delete texts[ev.model + ev.prompt];
          c.querySelector(".m").textContent = "Erreur"; c.querySelector(".md").textContent = ev.message;
          box.querySelectorAll(`[data-c^="${CSS.escape(ev.model)}|"]`).forEach((x) => { if (x.querySelector(".m").textContent === "en attente") x.querySelector(".m").textContent = "non lancé (erreur précédente)"; });
        }
      }
    }
    loadLab();
    $("labRunInfo").textContent = `Terminé en ${Math.round((Date.now() - t0) / 1000)} s. Compare surtout la qualité des réponses : c'est elle qui compte au quotidien.`;
  } catch (e) { $("labRunInfo").textContent = e.message; }
  finally { labRunning = false; $("labRun").disabled = false; setEmotion("idle"); }
};
