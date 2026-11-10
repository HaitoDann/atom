/* ============================================================
   NOTIFICATIONS WEB PUSH, INSTALLATION SUR LE TÉLÉPHONE, MISES À JOUR
   ============================================================ */
const pushSupported = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && isSecureContext;
const b64ToBytes = (s) => { const b = atob((s + "=".repeat((4 - (s.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/")); return Uint8Array.from(b, (c) => c.charCodeAt(0)); };
async function pushSub() { if (!pushSupported()) return null; const reg = await navigator.serviceWorker.ready; return reg.pushManager.getSubscription(); }
function deviceName() {
  const ua = navigator.userAgent;
  const m = ua.match(/Android [\d.]+; ([^;)]+)/) || ua.match(/(iPhone|iPad|Macintosh|Windows NT [\d.]+|Linux)/);
  return (m ? m[1].replace(/ Build.*$/, "") : "Appareil") + (matchMedia("(display-mode: standalone)").matches ? " · appli" : " · navigateur");
}
async function loadPush() {
  if (!pushSupported()) {
    $("pushOn").disabled = true; $("pushOff").hidden = $("pushTest").hidden = true;
    $("pushState").textContent = !isSecureContext ? "Les notifications demandent une adresse sécurisée : ouvre Atom via son adresse Tailscale https://…ts.net."
      : "Ce navigateur ne gère pas les notifications web.";
    return;
  }
  const sub = await pushSub().catch(() => null);
  let st = { devices: [] }; try { st = await getJSON("/api/push"); } catch {}
  const on = !!sub && Notification.permission === "granted";
  $("pushOn").hidden = on; $("pushOn").disabled = false; $("pushOff").hidden = $("pushTest").hidden = !on;
  $("pushState").textContent = (Notification.permission === "denied" ? "Notifications bloquées pour Atom : autorise-les dans les réglages du téléphone (Appli Atom → Notifications). " : "")
    + (st.devices.length ? `Appareils abonnés : ${st.devices.map((d) => d.device || "appareil").join(", ")}.` : "Aucun appareil abonné.");
}
async function pushEnable() {
  if (!pushSupported()) { toast("Les notifications demandent HTTPS (adresse Tailscale)."); return false; }
  const perm = await Notification.requestPermission();
  if (perm !== "granted") { toast("Notifications refusées. Tu peux les autoriser dans les réglages du téléphone."); loadPush(); return false; }
  try {
    const { public_key } = await getJSON("/api/push");
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(public_key) });
    await send_("/api/push/subscribe", "POST", { subscription: sub.toJSON(), device: deviceName() });
    toast("<b>Notifications activées</b> sur cet appareil.");
  } catch (e) { toast(`Activation impossible : ${esc(e.message)}`); return false; }
  loadPush(); agvTip();
  return true;
}
$("pushOn").onclick = pushEnable;
$("pushOff").onclick = async () => {
  const sub = await pushSub().catch(() => null);
  if (sub) { try { await send_("/api/push/unsubscribe", "POST", { endpoint: sub.endpoint }); } catch {} await sub.unsubscribe().catch(() => {}); }
  toast("Notifications désactivées sur cet appareil."); loadPush(); agvTip();
};
$("pushTest").onclick = async () => { try { await send_("/api/push/test", "POST"); toast("Notification envoyée."); } catch (e) { toast(esc(e.message)); } };

// Conseil en haut de l'agenda : activer les notifications (rappels avant chaque rendez-vous).
async function agvTip() {
  const tip = $("agvTip");
  if (!pushSupported()) {
    tip.hidden = isSecureContext;
    tip.innerHTML = "Pour recevoir les rappels en notification et installer Atom, ouvre-le via son adresse <b>Tailscale</b> (https://…ts.net).";
    return;
  }
  const sub = await pushSub().catch(() => null);
  if (sub && Notification.permission === "granted") { tip.hidden = true; return; }
  tip.hidden = false;
  tip.innerHTML = 'Reçois un rappel avant chaque rendez-vous sur ce téléphone. <button class="btn sm primary" type="button">Activer les notifications</button>';
  tip.querySelector("button").onclick = pushEnable;
}

// ---- Installation : bandeau sur téléphone tant que l'appli n'est pas installée
let instEvt = null;
const standalone = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone;
function instDismissed() { try { return +localStorage.getItem("atom.instDismissed") > Date.now() - 14 * 86400000; } catch { return false; } }
function showInstall() {
  if (standalone() || instDismissed() || !narrow()) { $("installBanner").hidden = true; return; }
  const ios = /iphone|ipad/i.test(navigator.userAgent);
  $("instGo").hidden = !instEvt;
  $("instText").textContent = instEvt ? "Une icône sur l'écran d'accueil, en plein écran, avec les notifications."
    : !isSecureContext ? "Ouvre Atom via son adresse Tailscale (https://…ts.net) : Chrome proposera alors de l'installer. L'adresse http://IP ne le permet pas."
    : ios ? "Bouton Partager → « Sur l'écran d'accueil »."
    : "Menu ⋮ de Chrome → « Installer l'application » (ou « Ajouter à l'écran d'accueil »).";
  $("installBanner").hidden = false;
}
addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); instEvt = e; showInstall(); });
addEventListener("appinstalled", () => { instEvt = null; $("installBanner").hidden = true; toast("<b>Atom est installé</b> · ouvre-le depuis l'écran d'accueil."); });
$("instGo").onclick = async () => { if (!instEvt) return; instEvt.prompt(); await instEvt.userChoice.catch(() => {}); instEvt = null; showInstall(); };
$("instClose").onclick = () => { try { localStorage.setItem("atom.instDismissed", String(Date.now())); } catch {} $("installBanner").hidden = true; };
setTimeout(showInstall, 1500);

// ---- Mises à jour : l'appli installée charge toujours la dernière version à l'ouverture. Si elle reste ouverte
// (Android la garde en mémoire), elle vérifie régulièrement et se recharge en revenant au premier plan.
const atomVersion = document.querySelector('meta[name="atom-version"]')?.content || "";
let newVersion = false;
async function checkVersion() {
  try {
    const v = (await (await fetch("/api/auth/status", { cache: "no-store" })).json()).version;
    if (v && atomVersion && v !== atomVersion && !newVersion) { newVersion = true; toast("<b>Nouvelle version d'Atom</b> · elle s'appliquera au prochain retour sur l'appli."); }
  } catch {}
}
setInterval(checkVersion, 10 * 60000);
document.addEventListener("visibilitychange", async () => {
  if (document.visibilityState !== "visible") return;
  await checkVersion();
  if (newVersion && !busy) location.reload();
});
