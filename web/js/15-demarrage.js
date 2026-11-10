"use strict";

/* ============================================================
   DÉMARRAGE
   ============================================================ */
applyLayout();
setBusy(false);
// La page elle-même ne doit jamais défiler (seules les zones internes défilent).
addEventListener("scroll", () => { if (scrollY || scrollX) scrollTo(0, 0); }, { passive: true });
let booted = false;
function boot() {
if (booted) return;
booted = true;
(async () => {
  const fromLink = parseInt(new URLSearchParams(location.search).get("c"), 10);
  if (fromLink) { settings.conversationId = fromLink; window.history.replaceState(null, "", "/"); }
  await loadConversations();
  if (settings.conversationId) await openConversation(settings.conversationId);
  else { renderHistory(); restoreDraft(); }
})();
connect();
applyLook();
renderWebBtn();
loadHybrid().then(loadWorkshop);
initVoice();
loadLibrary();
loadSpaces();
const viewParam = new URLSearchParams(location.search).get("view");   // lien d'une notification (ex. agenda)
if (viewParam === "agenda") { window.history.replaceState(null, "", "/"); showView("agenda"); }
else if (["code", "library", "agenda"].includes(store.get("view", "chat"))) showView(store.get("view", "chat"));
refreshCounts();
setInterval(refreshCounts, 60000);
checkNight();
setInterval(checkNight, 60000);
refreshPanel();
refreshSystem();
refreshMood();
setInterval(refreshMood, 120000);
setInterval(refreshSystem, 4000);
setInterval(refreshPanel, 30000);
setInterval(async () => {
  if (busy) return;
  connect();
  if (!settings.conversationId) return;
  try {
    const msgs = (await getJSON(`/api/conversations/${settings.conversationId}/messages`)).messages;
    if (!busy && msgs.length > history.length) {
      const last = msgs[msgs.length - 1];
      history = msgs; renderHistory();
      if (last.emotion) { setEmotion(last.emotion); scheduleRest(); }
      if (last.role === "assistant") presenceSay(last.content, "Nouveau message");
    }
  } catch {}
}, 15000);
scheduleRest();
input.focus();
}

/* ============================================================
   CONNEXION
   ============================================================ */
let loginSetup = false;
function showLogin(setup) {
  loginSetup = setup;
  $("login").hidden = false;
  $("loginPw2").hidden = !setup;
  $("loginPw").autocomplete = setup ? "new-password" : "current-password";
  $("loginText").textContent = setup ? "Bienvenue. Choisis le mot de passe qui protégera Atom." : "Entre ton mot de passe.";
  $("loginBtn").textContent = setup ? "Créer le mot de passe" : "Se connecter";
  $("loginNote").textContent = setup ? "8 caractères minimum. Cet appareil restera connecté." : "";
  $("loginErr").textContent = "";
  setTimeout(() => $("loginPw").focus(), 50);
}
$("loginForm").onsubmit = async (e) => {
  e.preventDefault();
  const pw = $("loginPw").value;
  if (loginSetup && pw !== $("loginPw2").value) { $("loginErr").textContent = "Les deux mots de passe sont différents."; return; }
  $("loginBtn").disabled = true;
  try {
    const r = await fetch(loginSetup ? "/api/auth/setup" : "/api/auth/login", { method: "POST",
      headers: { "Content-Type": "application/json", "X-Atom": "1" }, body: JSON.stringify({ password: pw }) });
    if (!r.ok) throw new Error((await r.json()).detail || "Échec");
    $("login").hidden = true; $("loginPw").value = ""; $("loginPw2").value = "";
    if (booted) location.reload(); else boot();
  } catch (err) { $("loginErr").textContent = err.message; }
  finally { $("loginBtn").disabled = false; }
};
(async () => {
  try {
    const s = await (await fetch("/api/auth/status")).json();
    if (s.authenticated) boot(); else showLogin(s.setup_needed);
  } catch { boot(); }
})();

/* État et sécurité */
async function loadStatus() {
  $("stInfo").textContent = "Vérification…";
  let r;
  try { r = await getJSON("/api/status"); } catch (e) { $("stInfo").textContent = e.message; return; }
  const n = { ok: 0, warn: 0, error: 0, off: 0 };
  r.checks.forEach((c) => n[c.status]++);
  $("stInfo").textContent = (r.status === "ok" ? "Tout fonctionne." : r.status === "warn" ? `${n.warn} point(s) à surveiller.` : `${n.error} problème(s) détecté(s).`) + ` Version ${r.version}.`;
  $("stList").innerHTML = r.checks.map((c) => `<li><span class="st-dot ${c.status}"></span><div><b>${esc(c.name)}</b>${esc(c.detail)}${c.hint ? `<br><code>${esc(c.hint)}</code>` : ""}</div></li>`).join("");
}
$("stRefresh").onclick = loadStatus;
async function loadSecurity() {
  let d;
  try { d = await getJSON("/api/security/sessions"); } catch { return; }
  $("secList").innerHTML = "";
  for (const s of d.sessions) {
    const li = document.createElement("li");
    li.style.cssText = "display:flex;align-items:center;gap:10px";
    li.innerHTML = `<div style="flex:1"><small>${s.id === d.current ? "cet appareil · " : ""}vu ${esc(new Date(s.last_seen * 1000).toLocaleString("fr-FR"))} · ${esc(s.ip || "")}</small>${esc(s.device || "Appareil")}</div>`;
    if (s.id !== d.current) {
      const b = document.createElement("button"); b.className = "btn sm"; b.textContent = "Déconnecter";
      b.onclick = async () => { await send_(`/api/security/sessions/${s.id}`, "DELETE"); loadSecurity(); };
      li.appendChild(b);
    }
    $("secList").appendChild(li);
  }
}
$("secLogout").onclick = async () => { await fetch("/api/auth/logout", { method: "POST", headers: { "X-Atom": "1" } }); location.reload(); };
$("secOthers").onclick = async () => {
  if (!confirm("Déconnecter tous les autres appareils ?")) return;
  const d = await getJSON("/api/security/sessions");
  for (const s of d.sessions) if (s.id !== d.current) await send_(`/api/security/sessions/${s.id}`, "DELETE");
  loadSecurity(); toast("Autres appareils déconnectés.");
};
$("secChange").onclick = async () => {
  try { await send_("/api/security/password", "POST", { current: $("secCur").value, new: $("secNew").value });
    $("secCur").value = ""; $("secNew").value = ""; toast("<b>Mot de passe changé</b> · les autres appareils sont déconnectés."); loadSecurity(); }
  catch (e) { toast(esc(e.message)); }
};
