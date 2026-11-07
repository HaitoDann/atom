"use strict";

/* Mode Code (suite) — voir 11a-code-explorateur.js. */
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
