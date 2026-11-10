"use strict";

/* ============================================================
   SAISIE ET ENVOI (streaming NDJSON)
   ============================================================ */
let serverSpeed = 0, engineOverride = null;
let busy = false, controller = null, idleTimer = 0, sleepTimer = 0, lastSpeed = null;

function autoGrow() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 220) + "px";
  sendBtn.disabled = !busy && !input.value.trim() && !pending.length;
}
function setBusy(b) {
  busy = b;
  sendBtn.classList.toggle("stop", b);
  sendBtn.innerHTML = icon(b ? "stop" : "up");
  sendBtn.title = b ? "Arrêter" : "Envoyer";
  autoGrow();
}
input.addEventListener("input", () => { autoGrow(); saveDraft(); entity.typingAt = performance.now(); entity.keyKick = 1; });
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!busy) form.requestSubmit(); }
  if (e.key === "ArrowUp" && !input.value && !busy) {
    const i = history.map((m) => m.role).lastIndexOf("user");
    if (i >= 0 && history[i].id) { e.preventDefault(); editMessage(i); }
  }
});
form.addEventListener("submit", (e) => {
  e.preventDefault();
  if (busy) { controller?.abort(); return; }
  const text = input.value.trim();
  if (pending.some((f) => f.loading)) { toast("Lecture du fichier en cours…"); return; }
  if (text || pending.length) {
    const files = pending.slice();
    pending = []; renderTray();
    input.value = ""; clearDraft(); autoGrow();
    const dataFile = files.find((f) => f.data);
    if (dataFile) sendSpecial("analyze", text || "", { name: dataFile.name, data: dataFile.b64, question: text || "" }, dataFile.name);
    else if (deepNext && text && !files.length) sendSpecial("research", text, { message: text });
    else if (workshopNext && text && !files.length) sendWorkshop(text);
    else routeAndSend(text, files);
  }
});

// Tâche difficile : selon le réglage (Réglages → Mode hybride → Tâches difficiles), Atom la confie directement à
// l'orchestration vérifiée. Les demandes simples et moyennes vont au bon modèle en direct (plus rapide).
async function routeAndSend(text, files = []) {
  if (text && !files.length) {
    try {
      const p = await send_("/api/route/plan", "POST", { message: text, engine: engineOverride || engine || "default" }).then((r) => r.json());
      if (p.orchestrate) {
        engineOverride = null;
        toast(`<b>Orchestration vérifiée</b> · ${esc(p.reason)}`);
        sendWorkshop(text, { pattern: "orchestra" });
        return;
      }
    } catch {}
  }
  sendMessage(text, files);
}

function scheduleRest() {
  clearTimeout(idleTimer); clearTimeout(sleepTimer);
  idleTimer = setTimeout(() => { if (!busy) { setEmotion("idle"); setEntityState("en attente"); } }, 9000);
  sleepTimer = setTimeout(() => { if (!busy) { setEmotion("sleep"); setEntityState("au repos"); } }, entity.night ? 60000 : 180000);
}

async function syncIds() {
  if (!settings.conversationId) return;
  try {
    const msgs = (await getJSON(`/api/conversations/${settings.conversationId}/messages`)).messages;
    if (busy) return;
    const keepBottom = atBottom();
    history = msgs;
    renderHistory();
    if (!keepBottom) scroller.scrollTop = scroller.scrollHeight;
  } catch {}
}

async function sendMessage(text, files = []) {
  if (busy) return;
  if (!text && !files.length) return;
  exitHero();
  $("empty")?.remove();
  setBusy(true);
  clearTimeout(idleTimer); clearTimeout(sleepTimer);

  const userMsg = { role: "user", content: text, meta: files.length ? { attachments: files.map((f) => ({ name: f.name, chars: f.text.length, pages: f.pages })) } : {} };
  history.push(userMsg);
  chat.appendChild(msgEl(userMsg, history.length - 1, true));
  markLast();
  scroller.scrollTop = scroller.scrollHeight;

  setEmotion("thinking");
  setEntityState("réflexion…");
  const el = document.createElement("div");
  el.className = "msg atom fresh";
  el.innerHTML = '<div class="body md"><span class="live"><span class="mini"></span><span>Atom réfléchit…</span></span></div>';
  chat.appendChild(el);
  scroller.scrollTop = scroller.scrollHeight;
  const body = el.querySelector(".body");

  let suggestOrch = "";
  let reply = "", emotion = "talking", queued = false, finished = false, tokens = 0, t0 = 0, used = null, asstId = null, sources = null, docs = null, provider = "local", remCards = [];
  const engineUsed = engineOverride || engine;
  engineOverride = null;
  const webMode = webForce ? "force" : (settings.webAuto === false ? "off" : "auto");
  if (webForce) { webForce = false; renderWebBtn(); }
  const render = () => {
    queued = false;
    const stick = atBottom();
    body.innerHTML = md(reply.trimStart());
    body.lastElementChild?.classList.add("cursor");
    if (stick) scroller.scrollTop = scroller.scrollHeight;
  };
  const finish = (stopped = false) => {
    if (finished) return;
    finished = true;
    const content = reply.trim() + (stopped && reply.trim() ? " …" : "");
    history.push({ role: "assistant", content: content || "…", emotion, id: asstId, created_at: Date.now() / 1000, meta: { ...(used ? { used } : {}), ...(sources ? { sources } : {}), ...(docs ? { docs } : {}), ...(provider !== "local" ? { provider: hybridState?.name || "Mistral", remote_model: hybridState?.model } : {}), ...(remCards.length ? { reminders: remCards } : {}) } });
    const done = msgEl(history[history.length - 1], history.length - 1);
    el.replaceWith(done);
    if (suggestOrch && !stopped) {
      // Tâche difficile : proposer de la refaire avec l'orchestration vérifiée (calculs exécutés, sources, juge).
      const b = document.createElement("button");
      b.className = "btn orch-suggest"; b.type = "button";
      b.innerHTML = `${icon("users")}Refaire avec l'orchestration vérifiée`; b.title = suggestOrch;
      b.onclick = () => { if (busy) return; b.remove(); sendWorkshop(text, { pattern: "orchestra" }); };
      done.appendChild(b);
    }
    markLast();
    [...done.querySelectorAll(".sources .src-l, .used summary")].slice(0, 6).forEach((c, k) => signalTo(c, 150 + k * 140));
    if (serverSpeed) { $("speedV").textContent = serverSpeed.toFixed(1) + " tok/s"; serverSpeed = 0; }
    else if (tokens > 3 && t0) { lastSpeed = tokens / ((performance.now() - t0) / 1000); $("speedV").textContent = lastSpeed.toFixed(1) + " tok/s"; }
    setEmotion(emotion);
    setEntityState("en attente");
    setBusy(false);
    scheduleRest();
    loadConversations();
    if (stopped) syncIds();
    presenceSay(content);
    if (!stopped && typeof voiceAfterReply === "function") voiceAfterReply(content);
    entity.feeding = false; entity.remote = false; entity.scan = false;
    setTimeout(refreshMood, 500);
    input.focus();
  };

  controller = new AbortController();
  try {
    const r = await api("/api/chat", {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({
        message: text, conversation_id: settings.conversationId, model: modelSel.value || settings.model || null,
        persona: settings.persona, auto_memory: settings.autoMemory,
        attachments: files.map((f) => ({ name: f.name, text: f.text })),
        web: webMode,
        scope,
        engine: engineUsed,
        space_id: settings.conversationId ? null : (settings.space || null),
      }),
    });
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === "meta") {
          if (settings.conversationId !== ev.conversation_id) { settings.conversationId = ev.conversation_id; saveSettings(); loadConversations(); }
        } else if (ev.type === "ids") {
          userMsg.id = ev.user_id; userMsg.created_at = Date.now() / 1000;
        } else if (ev.type === "context") {
          used = ev.used;
        } else if (ev.type === "route") {
          entity.remote = ev.provider !== "local";
          if (ev.provider === "local" && ev.reason) entity.glitch = 1;
          if (ev.provider !== "local") {
            body.innerHTML = `<span class="live"><span class="mini"></span><span>Atom consulte ${esc(hybridState?.name || "Mistral")}…</span></span>`;
            setEntityState("consulte…");
          }
          if (ev.reason && ev.provider === "local") toast(esc(ev.reason));
          provider = ev.provider;
        } else if (ev.type === "docs") {
          docs = ev.refs.length ? ev.refs : null;
          if (docs) {
            entity.scan = true;
            setEmotion("focus"); setEntityState("lit…");
            body.innerHTML = `<span class="live"><span class="mini"></span><span>Lecture de ${docs.length} passage${docs.length > 1 ? "s" : ""} de ta bibliothèque…</span></span>`;
          }
        } else if (ev.type === "reset") {
          reply = ""; tokens = 0; t0 = 0;
          body.innerHTML = '<span class="live"><span class="mini"></span><span>Atom réfléchit…</span></span>';
        } else if (ev.type === "search") {
          if (ev.status === "start") {
            entity.feedColor = [110, 170, 255]; entity.feeding = true; setEmotion("curious"); setEntityState("cherche…");
            body.innerHTML = `<span class="live"><span class="mini"></span><span>Recherche : <span class="q">${esc(ev.query)}</span></span></span>`;
          } else if (ev.status === "done") {
            entity.feeding = false; sources = ev.sources;
            body.innerHTML = `<span class="live"><span class="mini"></span><span>${ev.sources.length} sources lues, Atom rédige…</span></span>`;
          } else {
            entity.feeding = false;
            toast(`<b>Recherche impossible</b> · ${esc(ev.message || "")}`);
          }
        } else if (ev.type === "emotion") {
          emotion = ev.emotion; setEmotion(emotion); setEntityState("répond…");
        } else if (ev.type === "token") {
          if (!t0) { t0 = performance.now(); entity.remote = false; entity.scan = false; }
          tokens++;
          reply += ev.text;
          entity.tokenKick = 1;
          if (!queued) { queued = true; requestAnimationFrame(render); }
        } else if (ev.type === "agenda") {
          if (ev.action === "created") toast(`<b>📅 Ajouté à l'agenda</b> · ${esc(ev.when)} — ${esc(ev.title)}`);
          else if (ev.action === "cancelled") toast(`<b>Rendez-vous supprimé</b> · ${esc(ev.title)}`);
          else toast(`<b>Rendez-vous non ajouté</b> · ${esc(ev.message)}`);
          if (typeof loadAgendaView === "function" && currentView === "agenda") loadAgendaView();
        } else if (ev.type === "reminder") {
          if (ev.action === "created" || ev.action === "cancelled") { remCards.push(ev); pendingReminders = null; }
          if (ev.action === "created") toast(`<b>Rappel programmé</b> · ${esc(ev.when)} — ${esc(ev.text)}`);
          else if (ev.action === "cancelled") toast(`<b>Rappel annulé</b>`);
          else toast(`<b>Rappel non programmé</b> · ${esc(ev.message)}`);
          refreshPanel();
        } else if (ev.type === "done") {
          emotion = ev.emotion; asstId = ev.id; suggestOrch = ev.suggest_orchestra || "";
          if (ev.stats?.tok_s) { serverSpeed = ev.stats.tok_s; }
          finish();
        } else if (ev.type === "memory") {
          const list = ev.added.map((m) => esc(m.content.replace(/^L'utilisateur\s+/i, ""))).join(" · ");
          toast(`<b>Retenu</b> · ${list}`);
          const lastAtom = [...chat.querySelectorAll(".msg.atom")].pop();
          memoryFlight(lastAtom);
          lastAtom?.querySelector(".acts")?.before(memoryCard(ev.added));
          refreshPanel();
          if ($("settings").classList.contains("open")) loadMemories();
        } else if (ev.type === "error") {
          throw new Error(ev.message);
        }
      }
    }
    finish();
  } catch (err) {
    if (finished) return;
    entity.feeding = false; entity.remote = false; entity.scan = false;
    if (err.name === "AbortError") { finish(true); return; }
    finished = true;
    const msg = err instanceof TypeError ? "Serveur Atom injoignable." : err.message;
    const errEl = msgEl({ role: "assistant", content: msg, error: true }, -1);
    const row = document.createElement("div"); row.className = "row";
    const retry = document.createElement("button"); retry.className = "btn sm"; retry.innerHTML = icon("refresh") + "Réessayer";
    const edit = document.createElement("button"); edit.className = "btn sm"; edit.innerHTML = icon("edit") + "Modifier le message";
    const drop = async () => {
      if (userMsg.id && settings.conversationId) { try { await send_(`/api/conversations/${settings.conversationId}/truncate`, "POST", { from_id: userMsg.id }); } catch {} }
      const k = history.indexOf(userMsg); if (k >= 0) history.splice(k);
      renderHistory();
    };
    retry.onclick = async () => { await drop(); sendMessage(text, files); };
    edit.onclick = async () => { await drop(); pending = files.slice(); renderTray(); fillInput(text); };
    row.append(retry, edit);
    errEl.querySelector(".body").appendChild(row);
    el.replaceWith(errEl);
    setEmotion("fear"); entity.glitch = 1;
    setEntityState("erreur");
    setBusy(false);
    scheduleRest();
    connect();
  } finally {
    controller = null;
  }
}

/* boutons rapides */
const QUICK = [
  { i: "clock", t: "Rappel", fill: "Rappelle-moi " },
  { i: "list", t: "Mes rappels", send: "Quels sont mes rappels ?" },
  { i: "memory", t: "Retiens que…", fill: "Retiens que " },
  { i: "doc", t: "Résumer", send: "Résume notre conversation en quelques points." },
];
for (const q of QUICK) {
  const b = document.createElement("button");
  b.type = "button"; b.className = "qlink"; b.textContent = q.t;
  b.onclick = () => q.send ? sendMessage(q.send) : fillInput(q.fill);
  $("quick").appendChild(b);
}

/* raccourcis clavier */
document.addEventListener("keydown", (e) => {
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.shiftKey && e.key.toLowerCase() === "o") { e.preventDefault(); newConversation(); }
  else if (mod && e.key.toLowerCase() === "k") { e.preventDefault(); $("palette").classList.contains("open") ? closePalette() : openPalette(); }
  else if (e.key === "Escape" && presenceOn) { exitPresence(); }
  else if (e.key === "Escape") { closeSettings(); app.classList.remove("side-open", "panel-open"); applyLayout(); }
});
