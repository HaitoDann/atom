"use strict";

/* ============================================================
   ICÔNES (traits fins, monochromes)
   ============================================================ */
const ICONS = {
  plus: '<path d="M12 5.5v13M5.5 12h13"/>',
  search: '<circle class="f" cx="11" cy="11" r="6.5"/><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
  sidebar: '<rect class="f" x="3.5" y="4.5" width="6" height="15" rx="2.5"/><rect x="3.5" y="4.5" width="17" height="15" rx="3"/><path d="M9.5 4.5v15"/>',
  panel: '<rect class="f" x="14.5" y="4.5" width="6" height="15" rx="2.5"/><rect x="3.5" y="4.5" width="17" height="15" rx="3"/><path d="M14.5 4.5v15"/>',
  settings: '<path d="M4 7h8.5M16.5 7H20M4 12h3M11 12h9M4 17h10M18 17h2"/><circle class="f" cx="14.5" cy="7" r="2"/><circle cx="14.5" cy="7" r="2"/><circle class="f" cx="9" cy="12" r="2"/><circle cx="9" cy="12" r="2"/><circle class="f" cx="16" cy="17" r="2"/><circle cx="16" cy="17" r="2"/>',
  pin: '<path class="f" d="M9 4.5h6l-.8 5 3.3 3.2v1.8h-11v-1.8L9.8 9.5z"/><path d="M9 4.5h6l-.8 5 3.3 3.2v1.8h-11v-1.8L9.8 9.5zM12 14.5v5"/>',
  trash: '<path class="f" d="M6.5 7.5l.8 11.2A2 2 0 0 0 9.3 20.5h5.4a2 2 0 0 0 2-1.8l.8-11.2z"/><path d="M4.5 7.5h15M10 11v5.5M14 11v5.5M6.5 7.5l.8 11.2A2 2 0 0 0 9.3 20.5h5.4a2 2 0 0 0 2-1.8l.8-11.2M9.5 7.5V5.2c0-.4.3-.7.7-.7h3.6c.4 0 .7.3.7.7v2.3"/>',
  edit: '<path class="f" d="M15.6 5.4l3 3L9 18H6v-3z"/><path d="M15.6 5.4a2.1 2.1 0 0 1 3 3L9 18H6v-3zM13.8 7.2l3 3M5 20.5h14"/>',
  copy: '<rect class="f" x="8.5" y="8.5" width="11" height="11" rx="2.5"/><rect x="8.5" y="8.5" width="11" height="11" rx="2.5"/><path d="M15.5 8.5V6.5a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  refresh: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3l2.2 2.2M19.5 4.5v4.4h-4.4"/>',
  download: '<path d="M12 4.5v10.5M7.5 10.5L12 15l4.5-4.5M5 19.5h14"/>',
  eye: '<path class="f" d="M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"/><path d="M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
  up: '<path d="M12 18.5V6M6.5 11.5L12 6l5.5 5.5"/>',
  down: '<path d="M12 5.5V18M6.5 12.5L12 18l5.5-5.5"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="2.5"/>',
  mic: '<rect class="f" x="9" y="3.5" width="6" height="11" rx="3"/><rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v2.5"/>',
  speaker: '<path class="f" d="M4.5 9.5h3l4.5-4v13l-4.5-4h-3z"/><path d="M4.5 9.5h3l4.5-4v13l-4.5-4h-3zM15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
  x: '<path d="M7 7l10 10M17 7L7 17"/>',
  clock: '<circle class="f" cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v4.7l3 2"/>',
  memory: '<ellipse class="f" cx="12" cy="6.2" rx="7.5" ry="2.7"/><ellipse cx="12" cy="6.2" rx="7.5" ry="2.7"/><path d="M4.5 6.2v11.6c0 1.5 3.4 2.7 7.5 2.7s7.5-1.2 7.5-2.7V6.2M4.5 12c0 1.5 3.4 2.7 7.5 2.7s7.5-1.2 7.5-2.7"/>',
  list: '<path d="M9.5 6.5h10M9.5 12h10M9.5 17.5h10"/><circle cx="5" cy="6.5" r="1.1" fill="currentColor"/><circle cx="5" cy="12" r="1.1" fill="currentColor"/><circle cx="5" cy="17.5" r="1.1" fill="currentColor"/>',
  doc: '<path class="f" d="M6.5 4.5a1 1 0 0 1 1-1h6l4 4v12a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1z"/><path d="M7.5 3.5h6l4 4v12a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1zM13.5 3.5v4h4M9.5 12.5h5M9.5 16h5"/>',
  scale: '<path d="M12 4.5v15M8 19.5h8M5 8h14M5 8l-2.5 6a2.8 2.8 0 0 0 5 0zM19 8l-2.5 6a2.8 2.8 0 0 0 5 0z"/><circle cx="12" cy="4.5" r="1.2" fill="currentColor"/>',
  orb: '<circle class="f" cx="12" cy="12" r="5.5"/><circle cx="12" cy="12" r="5.5"/><ellipse cx="12" cy="12" rx="10" ry="3.4" transform="rotate(-16 12 12)"/><circle cx="20.6" cy="9.6" r="1.1" fill="currentColor"/>',
  user: '<circle class="f" cx="12" cy="8.5" r="3.5"/><circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5"/>',
  clip: '<path d="M19 11.5l-7.2 7.2a4.5 4.5 0 0 1-6.4-6.4l7.6-7.6a3 3 0 0 1 4.2 4.2l-7.6 7.6a1.5 1.5 0 0 1-2.1-2.1l7-7"/>',
  up2: '<path class="f" d="M7.5 10.5l4-7c1.4 0 2.3 1.1 2 2.4l-.8 3.6h5.4a2 2 0 0 1 2 2.3l-1.2 6.5a2 2 0 0 1-2 1.7H7.5z"/><path d="M7.5 10.5V20H4.5v-9.5zM7.5 10.5l4-7c1.4 0 2.3 1.1 2 2.4l-.8 3.6h5.4a2 2 0 0 1 2 2.3l-1.2 6.5a2 2 0 0 1-2 1.7H7.5"/>',
  down2: '<path class="f" d="M7.5 13.5l4 7c1.4 0 2.3-1.1 2-2.4l-.8-3.6h5.4a2 2 0 0 0 2-2.3l-1.2-6.5a2 2 0 0 0-2-1.7H7.5z"/><path d="M7.5 13.5V4H4.5v9.5zM7.5 13.5l4 7c1.4 0 2.3-1.1 2-2.4l-.8-3.6h5.4a2 2 0 0 0 2-2.3l-1.2-6.5a2 2 0 0 0-2-1.7H7.5"/>',
  spark: '<path class="f" d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9z"/><path d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9zM18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
  code: '<path d="M8.5 7.5L4 12l4.5 4.5M15.5 7.5L20 12l-4.5 4.5M13.5 5l-3 14"/>',
  folder: '<path class="f" d="M3.5 8.5h17v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  library: '<rect class="f" x="4.5" y="4.5" width="4" height="15" rx="1"/><rect x="4.5" y="4.5" width="4" height="15" rx="1"/><rect x="9.5" y="6.5" width="4" height="13" rx="1"/><path d="M15 6.8l3.6-1 3 13.3-3.6 1z"/>',
  globe: '<circle class="f" cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 3.6 5.4 3.6 8.5s-1.1 5.9-3.6 8.5c-2.5-2.6-3.6-5.4-3.6-8.5s1.1-5.9 3.6-8.5z"/>',
  users: '<circle class="f" cx="9" cy="9" r="3"/><circle cx="9" cy="9" r="3"/><circle cx="16.5" cy="10" r="2.4"/><path d="M3.5 19c.7-3 3-4.6 5.5-4.6s4.8 1.6 5.5 4.6M14.5 15c2.6-.4 5 .8 6 3.5"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  pulse: '<path d="M3.5 12h4l2.5-6 4 12 2.5-6h4"/>',
  lock: '<rect class="f" x="5" y="10.5" width="14" height="9.5" rx="2.5"/><rect x="5" y="10.5" width="14" height="9.5" rx="2.5"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/><circle cx="12" cy="15.2" r="1.2" fill="currentColor"/>',
};
const icon = (n) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;
document.querySelectorAll("[data-i]").forEach((el) => { el.insertAdjacentHTML("afterbegin", icon(el.dataset.i)); });
// Infobulle maison à la place de title= ; le nom du bouton est gardé (aria-label) pour les lecteurs d’écran.
document.querySelectorAll(".topbar .iconbtn[title], .composer .iconbtn[title], .side-bottom .iconbtn[title]").forEach((el) => { el.dataset.tip = el.title; if (!el.getAttribute("aria-label")) el.setAttribute("aria-label", el.title); el.removeAttribute("title"); });

/* ============================================================
   ÉTATS ÉMOTIONNELS — seule source de couleur de l'interface
   ============================================================ */
const ACTIVITIES = {
  idle:      { label: "Veille",       color: [196, 202, 212], radius: 1.0,  oscAmp: 3,   oscFreq: 0.8,  pulse: 0,     stretchY: 1,    spike: 0,    dim: 0.8  },
  thinking:  { label: "Réflexion",    color: [160, 140, 230], radius: 1.4,  oscAmp: 11,  oscFreq: 0.5,  pulse: 0,     stretchY: 1,    spike: 0.05, dim: 0.65, spin: 1.3 },
  talking:   { label: "Réponse",      color: [150, 200, 175], radius: 0.98, oscAmp: 5,   oscFreq: 1.5,  pulse: 0.05,  stretchY: 1,    spike: 0,    dim: 0.92 },
  joy:       { label: "Satisfaction", color: [236, 178, 120], radius: 1.06, oscAmp: 6,   oscFreq: 2.0,  pulse: 0.09,  stretchY: 0.97, spike: 0,    dim: 1.0  },
  curious:   { label: "Curiosité",    color: [130, 205, 225], radius: 1.1,  oscAmp: 5,   oscFreq: 1.1,  pulse: 0.02,  stretchY: 1.04, spike: 0,    dim: 0.95, swirl: 0.8, spin: 1.6 },
  concerned: { label: "Préoccupé",    color: [118, 138, 190], radius: 0.86, oscAmp: 1.6, oscFreq: 0.4,  pulse: 0,     stretchY: 0.88, spike: 0,    dim: 0.6,  spin: 0.45 },
  error:     { label: "Erreur",       color: [232, 70, 66],   radius: 1.04, oscAmp: 12,  oscFreq: 6,    pulse: 0.04,  stretchY: 1.02, spike: 0.18, dim: 0.95, jitter: 4, spin: 1.6 },
  sleep:     { label: "Sommeil",      color: [120, 128, 150], radius: 0.82, oscAmp: 0.8, oscFreq: 0.2,  pulse: 0.012, stretchY: 0.86, spike: 0,    dim: 0.42 },
};
// Anciennes émotions (réponses enregistrées, ancien modèle) → jeu réduit
const EMO_ALIAS = { angry: "concerned", sad: "concerned", fear: "concerned", surprise: "curious", focus: "thinking", content: "joy" };
const EMOTIONS = Object.keys(ACTIVITIES);
const VALENCE = { joy: 1, curious: 0.4, talking: 0.15, idle: 0.1, thinking: 0, sleep: -0.05, concerned: -0.6, error: -0.8 };
