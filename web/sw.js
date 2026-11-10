// Service worker d'Atom : rend l'appli installable et affiche l'interface
// même si le réseau flanche. L'API n'est jamais mise en cache.
const CACHE = "atom-shell-v5";
const SHELL = ["/", "/manifest.webmanifest", "/icons/icon-192.png?v=2", "/icons/icon-512.png?v=2", "/icons/badge-96.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  // Réseau d'abord (toujours la dernière version), cache en secours.
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
        return r;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("/")))
  );
});

// ---- Notifications (Web Push) : rappels, relances, agenda, brief — même appli fermée.
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { title: "Atom", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "Atom", {
    body: d.body || "", icon: "/icons/icon-192.png?v=2", badge: "/icons/badge-96.png",
    tag: d.tag ? `${d.tag}-${Date.now()}` : undefined, data: { url: d.url || "/" },
    actions: (d.actions || []).slice(0, 2),
  }));
});

self.addEventListener("notificationclick", (e) => {
  const n = e.notification, action = e.action, url = (n.data && n.data.url) || "/";
  n.close();
  e.waitUntil((async () => {
    if (action) {
      // Bouton (Fait, +1 h…) : traité sans ouvrir l'appli ; la session de l'appli est envoyée avec la requête.
      let msg = "";
      try {
        const r = await fetch("/api/push/action", { method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-Atom": "1" }, body: JSON.stringify({ action }) });
        const j = await r.json().catch(() => ({}));
        msg = r.ok ? (j.message || "C'est noté.") : (j.detail || "Action impossible : ouvre Atom pour te reconnecter.");
      } catch { msg = "Atom est injoignable (Tailscale actif ?)."; }
      return self.registration.showNotification("Atom", { body: msg, icon: "/icons/icon-192.png?v=2", badge: "/icons/badge-96.png", tag: "atom-ack" });
    }
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const w of wins) { if ("focus" in w) { w.navigate(url).catch(() => {}); return w.focus(); } }
    return self.clients.openWindow(url);
  })());
});
