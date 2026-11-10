/* ============================================================
   VOIX : dictée (serveur de transcription local) et lecture à voix haute
   ============================================================ */
let voiceState = { stt: false, tts_server: false }, rec = null, recChunks = [], voiceTurn = false, speaking = null;
const micBtn = $("micBtn");

async function initVoice() {
  try { voiceState = await getJSON("/api/voice"); } catch { return; }
  const canRecord = !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
  micBtn.hidden = !voiceState.stt || !canRecord;
  $("voiceAutoSend").checked = !!settings.voiceAutoSend;
  $("voiceRead").checked = settings.voiceRead !== false;
  $("voiceInfo").textContent = voiceState.stt
    ? (window.isSecureContext ? "Dicte avec le bouton micro de la saisie (transcription sur ton serveur), et écoute les réponses avec le bouton haut-parleur sous chaque réponse."
      : "Le micro du navigateur exige une adresse sécurisée : ouvre Atom en HTTPS (Tailscale) ou sur localhost. Les messages vocaux Telegram fonctionnent partout.")
    : "Dictée non activée : il faut le service de transcription (README → Voix). La lecture à voix haute fonctionne déjà avec la voix de ton appareil.";
}
$("voiceAutoSend").onchange = () => { settings.voiceAutoSend = $("voiceAutoSend").checked; saveSettings(); };
$("voiceRead").onchange = () => { settings.voiceRead = $("voiceRead").checked; saveSettings(); };

micBtn.onclick = async () => {
  if (rec && rec.state === "recording") { rec.stop(); return; }
  if (!window.isSecureContext) { toast("Le micro exige HTTPS (Tailscale) ou localhost. Les messages vocaux Telegram fonctionnent partout."); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { toast("Micro refusé ou indisponible."); return; }
  const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported?.(t)) || "";
  rec = new MediaRecorder(stream, type ? { mimeType: type } : {});
  recChunks = [];
  rec.ondataavailable = (e) => { if (e.data.size) recChunks.push(e.data); };
  rec.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    micBtn.classList.remove("rec"); micBtn.classList.add("busy"); micBtn.title = "Transcription…";
    setEntityState("j'écoute…");
    try {
      const blob = new Blob(recChunks, { type: rec.mimeType || "audio/webm" });
      const r = await fetch("/api/voice/transcribe", { method: "POST", body: blob, headers: { "Content-Type": blob.type.split(";")[0], "X-Atom": "1" } });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "transcription impossible");
      if (!j.text) { toast("Je n'ai rien entendu."); return; }
      input.value = (input.value.trim() ? input.value.trim() + " " : "") + j.text; autoGrow(); input.focus();
      voiceTurn = true;
      if (settings.voiceAutoSend) $("send").click();
    } catch (e) { toast(esc(e.message)); }
    finally { micBtn.classList.remove("busy"); micBtn.title = "Dicter (cliquer pour parler, recliquer pour finir)"; setEntityState("en attente"); }
  };
  rec.start();
  micBtn.classList.add("rec"); micBtn.title = "J'écoute… recliquer pour finir";
  setEmotion("curious"); setEntityState("j'écoute…");
};

function stopSpeaking() {
  if (speaking?.audio) speaking.audio.pause();
  if (window.speechSynthesis) speechSynthesis.cancel();
  speaking?.btn?.classList.remove("on"); speaking = null;
}
async function speakText(text, btn) {
  if (speaking) { const same = speaking.btn === btn; stopSpeaking(); if (same) return; }
  speaking = { btn }; btn?.classList.add("on");
  const done = () => { if (speaking?.btn === btn) { btn?.classList.remove("on"); speaking = null; setEmotion("idle"); } };
  setEmotion("talking");
  if (voiceState.tts_server) {
    try {
      const r = await api("/api/voice/speak", { method: "POST", body: JSON.stringify({ text }) });
      const audio = new Audio(URL.createObjectURL(await r.blob()));
      speaking.audio = audio; audio.onended = done; await audio.play(); return;
    } catch { /* repli : voix de l'appareil */ }
  }
  if (!window.speechSynthesis) { toast("La lecture à voix haute n'est pas disponible dans ce navigateur."); done(); return; }
  const clean = text.replace(/```[\s\S]*?```/g, " (bloc de code) ").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[*_`#>|]+/g, "").replace(/\[\d+\]/g, "");
  const u = new SpeechSynthesisUtterance(clean.slice(0, 6000));
  u.lang = "fr-FR";
  const fr = speechSynthesis.getVoices().filter((v) => v.lang?.toLowerCase().startsWith("fr"));
  u.voice = fr.find((v) => v.localService) || fr[0] || null;
  u.onend = done; u.onerror = done;
  speechSynthesis.speak(u);
}
// Après une réponse : lecture automatique si la question a été dictée.
function voiceAfterReply(content) {
  if (voiceTurn && settings.voiceRead !== false && content) speakText(content, null);
  voiceTurn = false;
}

