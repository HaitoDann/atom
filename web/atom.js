/* Atom — logique de l'interface (chargée par index.html, à la fin du corps de page). */
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
  up: '<path d="M12 18.5V6M6.5 11.5L12 6l5.5 5.5"/>',
  down: '<path d="M12 5.5V18M6.5 12.5L12 18l5.5-5.5"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="2.5"/>',
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
document.querySelectorAll(".topbar .iconbtn[title], .composer .iconbtn[title], .side-bottom .iconbtn[title]").forEach((el) => { el.dataset.tip = el.title; el.removeAttribute("title"); });

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

/* ============================================================
   ENTITÉ — sphère de fragments, un « familier » vivant
   Pas de traits humains : tout passe par les fragments (densité,
   vitesse, agitation, couleur, orbites).
   ============================================================ */
const entity = {
  activity: "idle", rippleT: 99, tokenKick: 0,
  typingAt: -1e9, keyKick: 0, absorb: 0, blink: 0,
  load: 0, mood: 0, night: false, hover: false,
  pet: 0, petting: -1e9, snuggle: 0, snuggling: false,
  feeding: false, level: 0, grow: 0,
  feedColor: [110, 170, 255],     // bleu = Internet, blanc = documents
  remote: false, remoteK: 0,      // consulte une IA distante : ondes qui partent de la sphère
  split: 0, splitK: 0, activeCluster: 0,   // atelier : la sphère se divise en amas qui dialoguent
  scan: false, scanK: 0,          // lecture (code, documents) : fragments alignés en lignes, balayage
  glitch: 0,                      // secours / erreur : brève perturbation
  seal: 0,                        // sauvegarde : contraction et anneau scellé
  fly: { p: 0, from: 0, to: 0, start: 0, dur: 900, active: false, onEnd: null },
  screen: { x: 0, y: 0, r: 0 },   // centre et rayon de la sphère à l'écran (pour les animations DOM)
};
let errorTimer = 0;
function setEmotion(e) {
  e = EMO_ALIAS[e] || e;
  if (!ACTIVITIES[e]) e = "talking";
  if (entity.activity === e) return;
  entity.activity = e;
  $("emoName").textContent = ACTIVITIES[e].label;
  clearTimeout(errorTimer);
  if (e === "error") errorTimer = setTimeout(() => { if (entity.activity === "error") setEmotion("idle"); }, 2600);   // l'erreur est brève
}
function setEntityState(t) { $("emoState").textContent = t; }

(function initEntity() {
  const canvas = document.getElementById("entity");
  const stage = document.getElementById("stage");
  const ctx = canvas.getContext("2d");
  const N = 3800, R0 = 100, F = 170;
  let W = 0, H = 0;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  // Le redimensionnement efface le canvas : on le fait en début d'image, juste avant de dessiner.
  function resize() {
    const r = stage.getBoundingClientRect();
    if (Math.abs(r.width - W) < 0.5 && Math.abs(r.height - H) < 0.5) return;
    W = r.width; H = r.height;
    canvas.width = Math.max(1, (W * dpr) | 0); canvas.height = Math.max(1, (H * dpr) | 0);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  let seed = 42;
  const rand = () => (seed = (seed * 16807) % 2147483647, (seed - 1) / 2147483646);
  const ax = new Float32Array(N), ay = new Float32Array(N), az = new Float32Array(N);
  const ux = new Float32Array(N), uy = new Float32Array(N), uz = new Float32Array(N), rN = new Float32Array(N);
  const px = new Float32Array(N), py = new Float32Array(N), pz = new Float32Array(N);
  const phase = new Float32Array(N), size = new Float32Array(N), depth = new Float32Array(N);
  const orbR = new Float32Array(N), orbSpeed = new Float32Array(N), isOrb = new Uint8Array(N), rank = new Float32Array(N);

  for (let i = 0; i < N; i++) {
    const orb = i % 7 === 0;             // ~14 % en orbite
    isOrb[i] = orb ? 1 : 0;
    rank[i] = rand();                    // ordre d'apparition quand Atom grandit
    if (!orb) {
      const u = rand() * 2 - 1, th = rand() * Math.PI * 2, shell = rand() < 0.75;
      const r = shell ? R0 * (0.94 + rand() * 0.06) : R0 * rand() * 0.85;
      const s = Math.sqrt(1 - u * u);
      ax[i] = r * s * Math.cos(th); ay[i] = r * u; az[i] = r * s * Math.sin(th);
      const inv = r > 1 ? 1 / r : 0;
      ux[i] = ax[i] * inv; uy[i] = ay[i] * inv; uz[i] = az[i] * inv;
      rN[i] = r / R0; depth[i] = shell ? 1 : 0.5;
    } else {
      orbR[i] = R0 * (1.4 + rand() * 0.75);
      orbSpeed[i] = (0.18 + rand() * 0.5) * (rand() < 0.5 ? 1 : -1);
    }
    phase[i] = rand() * Math.PI * 2;
    size[i] = 0.8 + rand() * 1.1;
    px[i] = (rand() - 0.5) * 600; py[i] = (rand() - 0.5) * 600; pz[i] = (rand() - 0.5) * 600;
  }

  // ---- Maillage : une partie des fragments de la coque deviennent des nœuds reliés à leurs voisins.
  const sxA = new Float32Array(N), syA = new Float32Array(N), szA = new Float32Array(N), visA = new Uint8Array(N);
  const isNode = new Uint8Array(N);
  const nodeIdx = [];
  // Répartition régulière : on ne garde un fragment de la coque que s'il est assez loin des nœuds déjà choisis.
  {
    const minD2 = (R0 * 0.135) ** 2;
    for (let i = 0; i < N && nodeIdx.length < 360; i++) {
      if (isOrb[i] || rN[i] < 0.92) continue;
      let ok = true;
      for (const j of nodeIdx) { if ((ax[i] - ax[j]) ** 2 + (ay[i] - ay[j]) ** 2 + (az[i] - az[j]) ** 2 < minD2) { ok = false; break; } }
      if (ok) { isNode[i] = 1; nodeIdx.push(i); rank[i] = 0; }   // les nœuds sont toujours visibles
    }
  }
  const edges = [];   // [a, b, longueur au repos]
  {
    const K = 6, seen = new Set();
    for (const a of nodeIdx) {
      const near = nodeIdx.filter((b) => b !== a)
        .map((b) => [b, (ax[a] - ax[b]) ** 2 + (ay[a] - ay[b]) ** 2 + (az[a] - az[b]) ** 2])
        .sort((p, q) => p[1] - q[1]).slice(0, K);
      for (const [b, d2] of near) {
        if (d2 > (R0 * 0.42) ** 2) continue;   // pas de lien qui traverse la sphère
        const key = a < b ? a * N + b : b * N + a;
        if (!seen.has(key)) { seen.add(key); edges.push([a, b]); }
      }
    }
  }
  // Quelques orbiteurs reliés entre eux : un anneau de réseau autour de la sphère.
  const orbNodes = [];
  for (let i = 0; i < N && orbNodes.length < 18; i++) if (isOrb[i]) orbNodes.push(i);
  orbNodes.sort((a, b) => phase[a] - phase[b]);
  // Signaux : de la lumière qui voyage le long des liens.
  const SIG = 90, sgE = new Int32Array(SIG).fill(-1), sgT = new Float32Array(SIG), sgV = new Float32Array(SIG);
  let sigAcc = 0;
  const bucketPaths = Array.from({ length: 10 }, () => null);

  // Fragments « nourriture » (recherche web) : ils arrivent de l'extérieur et sont absorbés.
  const fx = new Float32Array(F), fy = new Float32Array(F), fv = new Float32Array(F), fa = new Uint8Array(F), fs = new Float32Array(F);
  function spawnFeeder(i, R) {
    const a = rand() * Math.PI * 2, d = R * (2.6 + rand() * 1.8);
    fx[i] = Math.cos(a) * d; fy[i] = Math.sin(a) * d * 0.8; fv[i] = 20 + rand() * 40; fa[i] = 1; fs[i] = 1 + rand() * 1.6;
  }

  const KEYS = ["radius", "oscAmp", "oscFreq", "pulse", "stretchY", "spike", "dim", "jitter", "swirl", "spin", "purr"];
  const DEF = { jitter: 0, swirl: 0, spin: 1, purr: 0 };
  const A0 = { ...DEF, ...ACTIVITIES.idle };
  const cur = { r: A0.color[0], g: A0.color[1], b: A0.color[2] };
  for (const k of KEYS) cur[k] = A0[k];
  const gaze = { x: 0, y: 0, tx: 0, ty: 0 };
  const mouse = { x: 0, y: 0, active: false, sx: 0, sy: 0, t: 0 };

  // ---- regard
  addEventListener("pointermove", (e) => {
    const r = stage.getBoundingClientRect();
    const cx = entity.screen.x, cy = entity.screen.y;
    const dx = e.clientX - cx, dy = e.clientY - cy, d = Math.hypot(dx, dy) || 1;
    const k = Math.min(1, d / 600);
    gaze.tx = (dx / d) * k * 14; gaze.ty = (dy / d) * k * 10;
    const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    entity.hover = inside;
    mouse.active = inside;
    const sc = entity.screen.scale || 1;
    mouse.x = dx / sc; mouse.y = dy / sc;
  });
  document.addEventListener("pointerleave", () => { mouse.active = false; entity.hover = false; gaze.tx = gaze.ty = 0; });

  entity.wasLongPress = () => false;

  const MOOD_NEG = [130, 150, 205], MOOD_POS = [228, 190, 150];
  let nextBlink = 6, nextGlance = 9;
  const ease = (x) => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;

  /* ---------------------------------------------------------------- apparence « Orbe »
     Une sphère métallique articulée (monochrome) : 5 bandes qui pivotent indépendamment comme un
     casse-tête, gravures-circuits et médaillons en relief, impulsions de lumière dans les gravures.
     Les émotions passent par la façon de tourner et la couleur de la lumière.
     Grosses tâches (recherche, atelier, IA distante, agent) : l'orbe s'ouvre et projette une carte de points. */
  const orb = (() => {
    // ---- « Planète vivante » : continents, relief, nuages, lune, météo — tout en traits monochromes
    const R2 = Math.random;
    const norm = (v) => { const l = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / l, v[1] / l, v[2] / l]; };
    const basis = (c) => { const up = Math.abs(c[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0]; const u = norm([up[1] * c[2] - up[2] * c[1], up[2] * c[0] - up[0] * c[2], up[0] * c[1] - up[1] * c[0]]); return [u, [c[1] * u[2] - c[2] * u[1], c[2] * u[0] - c[0] * u[2], c[0] * u[1] - c[1] * u[0]]]; };
    // point à la distance angulaire r de c, dans la direction a
    const geo = (c, u, v, r, a, alt = 1) => { const cr = Math.cos(r), sr = Math.sin(r), ca = Math.cos(a), sa = Math.sin(a); return [(c[0] * cr + (u[0] * ca + v[0] * sa) * sr) * alt, (c[1] * cr + (u[1] * ca + v[1] * sa) * sr) * alt, (c[2] * cr + (u[2] * ca + v[2] * sa) * sr) * alt]; };
    const lines = [];   // { pts, kind: "coast" | "topo" | "ridge", len }
    const continents = [];
    const NC = 9;
    for (let k = 0; k < NC; k++) {
      // répartition régulière (spirale de Fibonacci) pour qu'il y ait toujours des terres en vue
      const yk = 1 - (k + 0.5) / NC * 2, rk = Math.sqrt(1 - yk * yk), ak = k * 2.39996 + R2() * 0.4;
      const c = norm([Math.cos(ak) * rk, yk * 0.85, Math.sin(ak) * rk]), [u, v] = basis(c);
      const rb = 0.26 + R2() * 0.3, harm = Array.from({ length: 5 }, (_, i) => [0.08 + R2() * 0.16 / (i + 1), R2() * 6.28]);
      const rad = (a, f) => rb * f * (1 + harm.reduce((s, [am, ph], i) => s + am * Math.sin((i + 2) * a + ph), 0));
      continents.push({ c, u, v, rb });
      for (const [f, kind] of [[1, "coast"], [0.66, "topo"], [0.38, "topo"]]) {
        if (kind === "topo" && rb * f < 0.08) continue;
        const pts = []; for (let i = 0; i <= 72; i++) { const a = (i / 72) * Math.PI * 2; pts.push(geo(c, u, v, rad(a + (f < 1 ? 0.3 : 0), f), a)); }
        lines.push({ pts, kind });
      }
      // chaînes de montagnes : petits chevrons alignés
      for (let m = 0; m < (rb > 0.35 ? 2 : 1); m++) {
        const a0 = R2() * 6.28, r0 = rb * (0.15 + R2() * 0.35);
        for (let j = 0; j < 5; j++) {
          const a = a0 + j * 0.25 / Math.max(0.1, r0 * 4), r = r0 + j * 0.02, w = 0.025;
          const p0 = geo(c, u, v, r - w, a - 0.06), p1 = geo(c, u, v, r + w * 1.3, a), p2 = geo(c, u, v, r - w, a + 0.06);
          lines.push({ pts: [p0, p1, p2], kind: "ridge" });
        }
      }
    }
    // vagues des océans : petits « ~ » loin des côtes
    const waves = [];
    for (let k = 0; k < 70; k++) {
      const p = norm([R2() * 2 - 1, R2() * 2 - 1, R2() * 2 - 1]);
      if (continents.some((c) => Math.acos(Math.max(-1, Math.min(1, p[0] * c.c[0] + p[1] * c.c[1] + p[2] * c.c[2]))) < c.rb * 1.35)) continue;
      const [u, v] = basis(p);
      waves.push(Array.from({ length: 7 }, (_, i) => geo(p, u, v, 0.03 * Math.abs(i - 3) / 3 + 0.0001, i < 3 ? Math.PI : 0).map((x, j) => x + v[j] * Math.sin(i * 1.6) * 0.008)));
    }
    for (const l of lines) { l.len = 0; for (let i = 1; i < l.pts.length; i++) l.len += Math.hypot(l.pts[i][0] - l.pts[i - 1][0], l.pts[i][1] - l.pts[i - 1][1], l.pts[i][2] - l.pts[i - 1][2]); l.phase = R2(); }
    // nuages : traits ondulés à basse altitude
    const clouds = Array.from({ length: 9 }, () => {
      const lat = (R2() - 0.5) * 2.2, lon = R2() * 6.28, len = 0.35 + R2() * 0.5;
      return { lat, lon, len, wob: R2() * 6.28, speed: 0.6 + R2() * 0.8 };
    });
    const storm = { c: norm([0.3, 0.25, 0.9]), k: 0 };
    let yaw = R2() * 6.28, cloudYaw = 0, moonA = R2() * 6.28, satA = 0, openK = 0, stormK = 0, flash = 0, flashT = 0;
    const tilt = 0.41;   // inclinaison de l'axe

    function step(dt, st) {
      yaw += dt * st.spin;
      cloudYaw += dt * st.spin * st.cloudSpeed;
      moonA += dt * 0.22 * (st.spin / 0.11);
      satA += dt * 0.9;
      openK += ((st.open ? 1 : 0) - openK) * Math.min(1, dt * 2);
      stormK += ((st.storm ? 1 : 0) - stormK) * Math.min(1, dt * 1.5);
      flashT -= dt;
      if (st.lightning && flashT <= 0) { flash = 1; flashT = 0.25 + R2() * 0.9; storm.bolt = { c: norm([R2() - 0.5, R2() * 0.6 - 0.2, 0.8 + R2() * 0.2]), seed: R2() }; }
      flash *= Math.exp(-dt * 9);
    }
    // rotation de la planète puis projection (axe incliné)
    const T = [0, 0, 0];
    function proj(p, R, spin, out) {
      const c = Math.cos(spin), s = Math.sin(spin);
      const x = p[0] * c + p[2] * s, z = -p[0] * s + p[2] * c;
      const ct = Math.cos(tilt), stt = Math.sin(tilt);
      const y = p[1] * ct - z * stt, z2 = p[1] * stt + z * ct;
      out[0] = x * R; out[1] = -y * R; out[2] = z2;
      return out;
    }
    const L = norm([-0.8, 0.38, 0.45]);   // lumière (haut gauche, de côté : une belle face de nuit)

    function draw(ctx, st) {
      const R = st.R, A = st.alpha, px = st.px, lit = st.lit, tint = st.tint;
      const light = document.documentElement.dataset.theme === "light";
      const ink = light ? "40,40,40" : tint, bgc = getComputedStyle(document.body).backgroundColor;
      ctx.save(); ctx.lineCap = "round"; ctx.lineJoin = "round";
      const stroke = (a, w, col = ink) => { ctx.globalAlpha = Math.max(0, Math.min(1, a)) * A; ctx.lineWidth = w * px; ctx.strokeStyle = `rgb(${col})`; };
      // --- lune et orbite (moitié arrière, avant la planète)
      const orbit = (front) => {
        const OR = R * 1.62, ry = OR * 0.26, rot = -0.28;
        ctx.save(); ctx.rotate(rot);
        stroke(0.22, 0.7); ctx.setLineDash([3 * px, 5 * px]);
        ctx.beginPath(); ctx.ellipse(0, 0, OR, ry, 0, front ? 0 : Math.PI, front ? Math.PI : Math.PI * 2); ctx.stroke();
        ctx.setLineDash([]);
        const inFront = Math.sin(moonA) > 0;
        if (inFront === front) {
          const mx = Math.cos(moonA) * OR, my = Math.sin(moonA) * ry, mr = R * 0.13;
          ctx.fillStyle = bgc; ctx.globalAlpha = A; ctx.beginPath(); ctx.arc(mx, my, mr, 0, Math.PI * 2); ctx.fill();
          stroke(0.75, 1); ctx.stroke();
          stroke(0.35, 0.6);   // croissant d'ombre en hachures
          for (let k = -3; k <= 3; k++) { const yy = my + k * mr * 0.25, hw = Math.sqrt(Math.max(0, mr * mr - (yy - my) ** 2)); ctx.beginPath(); ctx.moveTo(mx + hw * 0.15, yy); ctx.lineTo(mx + hw, yy); ctx.stroke(); }
        }
        ctx.restore();
      };
      orbit(false);
      // --- atmosphère qui respire
      const br = 1 + Math.sin(st.t * 0.8) * 0.006;
      stroke(0.14 + lit * 0.12, 0.8); ctx.beginPath(); ctx.arc(0, 0, R * 1.07 * br, 0, Math.PI * 2); ctx.stroke();
      stroke(0.06 + lit * 0.06, 0.6); ctx.beginPath(); ctx.arc(0, 0, R * 1.14 * br, 0, Math.PI * 2); ctx.stroke();
      // disque opaque : cache ce qui passe derrière
      ctx.globalAlpha = A; ctx.fillStyle = bgc; ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fill();
      // --- face de nuit en hachures
      ctx.save(); ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.clip();
      const hs = R * 0.055;
      for (let k = -24; k <= 24; k++) {
        const off = k * hs;
        ctx.beginPath(); let pen = false;
        for (let j = 0; j <= 30; j++) {
          const tt = (j / 30) * 2 - 1, x = off * 0.7 + tt * R * 0.7, y = -off * 0.7 + tt * R * 0.7;   // diagonales
          const d2 = 1 - (x * x + y * y) / (R * R); if (d2 <= 0) { pen = false; continue; }
          const nz = Math.sqrt(d2), dot = (x / R) * L[0] + (-y / R) * L[1] + nz * L[2];
          const thr = -0.05 - (k % 2 ? 0.25 : 0);   // une ligne sur deux commence plus loin : dégradé
          if (dot < thr) { if (!pen) { ctx.moveTo(x, y); pen = true; } else ctx.lineTo(x, y); } else pen = false;
        }
        stroke(st.night * 0.5, 0.65); ctx.stroke();
      }
      ctx.restore();
      // --- continents : côtes, relief, montagnes, avec de la lumière qui court le long des côtes
      const shade = (p3) => { const d = p3[0] / R * L[0] + -p3[1] / R * L[1] + p3[2] * L[2]; return d > 0 ? 1 : 0.45 + 0.55 * (1 + d); };
      const pa = [0, 0, 0], pb = [0, 0, 0];
      const [h0] = toHsl(tint);
      for (const ln of lines) {
        const w = ln.kind === "coast" ? 1.15 : ln.kind === "topo" ? 0.6 : 0.8, a0 = ln.kind === "coast" ? 0.85 : ln.kind === "topo" ? 0.35 : 0.55;
        let s = 0;
        for (let i = 1; i < ln.pts.length; i++) {
          proj(ln.pts[i - 1], R, yaw, pa); proj(ln.pts[i], R, yaw, pb);
          const seg = Math.hypot(ln.pts[i][0] - ln.pts[i - 1][0], ln.pts[i][1] - ln.pts[i - 1][1], ln.pts[i][2] - ln.pts[i - 1][2]); s += seg;
          if (pa[2] < 0 && pb[2] < 0) continue;
          const edge = Math.min(1, (pa[2] + pb[2]) * 2.5);   // fondu au bord
          stroke(a0 * edge * shade(pa), w); ctx.beginPath(); ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]); ctx.stroke();
          if (ln.kind !== "coast") continue;
          const wave = Math.pow(Math.max(0, Math.sin((s / 0.45 - st.t * st.flow + ln.phase * 5) * Math.PI)), 12) * (0.2 + lit * 0.9) * edge;
          if (wave > 0.04) {
            const hue = h0 + Math.sin(s * 3 + st.t * 0.4) * st.hueSpread;
            ctx.globalAlpha = A * Math.min(1, wave); ctx.strokeStyle = `hsl(${hue.toFixed(0)},70%,${light ? 42 : 66}%)`; ctx.lineWidth = 1.7 * px; ctx.stroke();
            ctx.globalAlpha = A * wave * 0.2; ctx.lineWidth = 5 * px; ctx.stroke();
          }
        }
      }
      // --- vagues
      for (const wv of waves) {
        ctx.beginPath(); let pen = false;
        for (const p of wv) { proj(p, R, yaw, T); if (T[2] < 0.1) { pen = false; continue; } if (!pen) { ctx.moveTo(T[0], T[1]); pen = true; } else ctx.lineTo(T[0], T[1]); }
        stroke(0.28 * (0.5 + 0.5 * T[2]) * shade(T), 0.6); ctx.stroke();
      }
      // --- tempête en spirale (réflexion / curiosité)
      if (stormK > 0.02) {
        const [u, v] = basis(storm.c), sp = st.t * 1.6;
        ctx.beginPath(); let pen = false;
        for (let k = 0; k <= 60; k++) {
          const r = 0.01 + k * 0.0035, a = -k * 0.32 + sp;
          proj(geo(storm.c, u, v, r, a, 1.015), R, cloudYaw + yaw, T);
          if (T[2] < 0) { pen = false; continue; }
          if (!pen) { ctx.moveTo(T[0], T[1]); pen = true; } else ctx.lineTo(T[0], T[1]);
        }
        stroke(0.7 * stormK, 0.9); ctx.stroke();
      }
      // --- nuages : traits ondulés qui dérivent
      for (const cl of clouds) {
        ctx.beginPath(); let pen = false, zs = 0, n = 0;
        for (let k = 0; k <= 16; k++) {
          const lon = cl.lon + (k / 16) * cl.len, lat = cl.lat + Math.sin(k * 0.8 + cl.wob + st.t * 0.3) * 0.03;
          const p = [Math.cos(lat) * Math.cos(lon) * 1.03, Math.sin(lat) * 1.03, Math.cos(lat) * Math.sin(lon) * 1.03];
          proj(p, R, cloudYaw * cl.speed + yaw, T);
          if (T[2] < 0.05) { pen = false; continue; }
          zs += T[2]; n++;
          if (!pen) { ctx.moveTo(T[0], T[1]); pen = true; } else ctx.lineTo(T[0], T[1]);
        }
        if (!n) continue;
        stroke((0.3 + (st.rain ? 0.2 : 0)) * Math.min(1, zs / n * 2), 1.1); ctx.stroke();
        if (st.rain) {   // pluie : petits traits obliques sous le nuage
          const lon = cl.lon + cl.len / 2, p = [Math.cos(cl.lat) * Math.cos(lon), Math.sin(cl.lat), Math.cos(cl.lat) * Math.sin(lon)];
          proj(p, R, cloudYaw * cl.speed + yaw, T);
          if (T[2] > 0.2) { stroke(0.35, 0.6); for (let k = 0; k < 4; k++) { const x = T[0] + (k - 1.5) * R * 0.03, y = T[1] + R * 0.02 + ((st.t * 40 + k * 7) % 10) * R * 0.004; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - R * 0.012, y + R * 0.03); ctx.stroke(); } }
        }
      }
      // --- éclairs (colère)
      if (flash > 0.05 && storm.bolt) {
        proj(storm.bolt.c, R, yaw, T);
        if (T[2] > 0) {
          let x = T[0], y = T[1] - R * 0.05;
          ctx.beginPath(); ctx.moveTo(x, y);
          for (let k = 0; k < 5; k++) { x += (Math.sin(storm.bolt.seed * 50 + k * 3) * 0.5) * R * 0.05; y += R * 0.035; ctx.lineTo(x, y); }
          ctx.globalAlpha = A * flash; ctx.strokeStyle = `rgb(${tint})`; ctx.lineWidth = 1.4 * px; ctx.stroke();
        }
      }
      // --- aurores aux pôles (activité, joie)
      if (st.aurora > 0.02) {
        for (const pole of [1, -1]) {
          for (let k = 0; k < 40; k++) {
            const lon = (k / 40) * Math.PI * 2, lat = pole * (1.2 + Math.sin(lon * 3 + st.t * 0.7) * 0.05);
            const base = [Math.cos(lat) * Math.cos(lon), Math.sin(lat), Math.cos(lat) * Math.sin(lon)];
            const hgt = 1.04 + 0.05 * (0.5 + 0.5 * Math.sin(lon * 5 + st.t * 2.2));
            proj(base.map((x) => x * 1.01), R, yaw, pa); proj(base.map((x) => x * hgt), R, yaw, pb);
            if (pa[2] < 0) continue;
            const hue = h0 + Math.sin(lon * 2 + st.t) * st.hueSpread;
            ctx.globalAlpha = A * st.aurora * 0.7 * (0.4 + 0.6 * pa[2]); ctx.strokeStyle = `hsl(${hue.toFixed(0)},70%,${light ? 45 : 65}%)`; ctx.lineWidth = 0.9 * px;
            ctx.beginPath(); ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]); ctx.stroke();
          }
        }
      }
      // --- contour de la planète
      stroke(0.85, 1.2); ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.stroke();
      // --- satellites et signaux (grosses tâches)
      if (openK > 0.02) {
        for (let k = 0; k < 3; k++) {
          const a = satA * (1 + k * 0.15) + k * 2.1, SR = R * (1.32 + k * 0.08);
          const sx = Math.cos(a) * SR, sy = Math.sin(a) * SR * 0.45 - R * 0.1 * k;
          if (Math.sin(a) < 0 && Math.hypot(sx, sy) < R) continue;   // caché derrière
          stroke(0.9 * openK, 1.1); ctx.strokeRect(sx - R * 0.03, sy - R * 0.022, R * 0.06, R * 0.044);
          for (const sg of [-1, 1]) { ctx.strokeRect(sx + sg * R * 0.05 - (sg < 0 ? R * 0.07 : 0), sy - R * 0.018, R * 0.07, R * 0.036); }   // panneaux solaires
          // faisceau vers la surface, en impulsions
          const tx = sx * 0.55, ty = sy * 0.55, pulse = (st.t * 1.5 + k * 0.33) % 1;
          stroke(0.25 * openK, 0.7); ctx.setLineDash([2 * px, 4 * px]); ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(tx, ty); ctx.stroke(); ctx.setLineDash([]);
          ctx.globalAlpha = A * openK; ctx.strokeStyle = `hsl(${(h0 + k * 20).toFixed(0)},70%,${light ? 42 : 66}%)`; ctx.lineWidth = 1.6 * px;
          const qx = sx + (tx - sx) * pulse, qy = sy + (ty - sy) * pulse;
          ctx.beginPath(); ctx.moveTo(qx, qy); ctx.lineTo(qx + (tx - sx) * 0.08, qy + (ty - sy) * 0.08); ctx.stroke();
        }
      }
      orbit(true);
      ctx.restore();
    }
    const toHsl = (rgb) => {
      const [r, g, b] = rgb.split(",").map((x) => +x / 255), mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
      if (mx === mn) return [0, 0, l];
      const d = mx - mn, h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
      return [h * 60, 0, l];
    };
    return { step, draw };
  })();

  let last = performance.now(), t = 0;
  function frame(now) {
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now; t += dt;
    requestAnimationFrame(frame);
    if (document.hidden) return;

    // ---- vol panneau ⇄ plein écran : une seule courbe, pilotée ici
    const fl = entity.fly;
    if (fl.active) {
      const k = Math.min(1, (now - fl.start) / fl.dur);
      fl.p = fl.from + (fl.to - fl.from) * ease(k);
      if (k >= 1) { fl.active = false; fl.p = fl.to; const cb = fl.onEnd; fl.onEnd = null; cb && cb(); }
    }
    resize();
    if (W < 10 || H < 10) return;
    const P = fl.p;

    const A = { ...DEF, ...ACTIVITIES[entity.activity] };
    const typing = now - entity.typingAt < 1400;
    const isIdle = entity.activity === "idle" || entity.activity === "sleep";
    entity.rippleT += dt;


    // ---- micro-comportements
    if (typing && P < 0.5) { gaze.tx = -16; gaze.ty = 9; }
    gaze.x += (gaze.tx - gaze.x) * Math.min(1, dt * 3);
    gaze.y += (gaze.ty - gaze.y) * Math.min(1, dt * 3);
    entity.blink = Math.max(0, entity.blink - dt * 6);
    entity.keyKick *= Math.exp(-dt * 7);
    // ---- une seule animation « travail long » : recherche, indexation, lecture, agent, IA distante, atelier
    if (entity.glitch > 0.5) setEmotion("error");          // ancien signal d'erreur → état Erreur
    const work = entity.feeding || entity.remote || entity.split > 0 || entity.scan;
    entity.workC = entity.remote ? [205, 195, 255] : entity.split > 0 ? [236, 190, 130] : entity.scan ? [225, 225, 232] : entity.feeding ? entity.feedColor : (entity.workC || [110, 170, 255]);
    entity.workK = (entity.workK || 0) + ((work ? 1 : 0) - (entity.workK || 0)) * Math.min(1, dt * 2.5);
    entity.blink = 0; entity.grow = 0; entity.seal = 0; entity.glitch = 0; entity.absorb = 0; entity.rippleT = 99;
    entity.remote = entity.remote; entity.mood = 0; entity.night = false; entity.load = 0;
    entity.absorb *= Math.exp(-dt * 2.2);
    entity.tokenKick *= Math.exp(-dt * 9);
    entity.grow *= Math.exp(-dt * 0.9);
    entity.glitch *= Math.exp(-dt * 2.5);
    entity.seal *= Math.exp(-dt * 1.4);
    entity.remoteK = 0; entity.scanK = 0; entity.splitK = 0;   // anciennes animations (ondes, lignes, amas) retirées

    // ---- cible : émotion, puis caresse, humeur, nuit, charge, attention
    const T = { r: A.color[0], g: A.color[1], b: A.color[2] };
    for (const k of KEYS) T[k] = A[k];
    const pw = entity.pet;
    if (isIdle && entity.mood && pw < 0.5) {
      const m = Math.max(-1, Math.min(1, entity.mood)), c = m > 0 ? MOOD_POS : MOOD_NEG, w = Math.abs(m) * 0.35;
      T.r += (c[0] - T.r) * w; T.g += (c[1] - T.g) * w; T.b += (c[2] - T.b) * w;
    }
    if (entity.night) { T.dim *= 0.72; T.r *= 0.86; T.g *= 0.9; T.oscFreq *= 0.75; }
    if (typing) { T.radius *= 1.04; T.dim = Math.min(1, T.dim + 0.12); }
    if (entity.workK > 0.01) {
      const w = entity.workK, c = entity.workC;
      T.radius *= 1 + 0.05 * w; T.spin *= 1 + 0.6 * w; T.dim = Math.min(1, T.dim + 0.1 * w);
      T.r += (c[0] - T.r) * 0.3 * w; T.g += (c[1] - T.g) * 0.3 * w; T.b += (c[2] - T.b) * 0.3 * w;   // la maille prend un peu la couleur de la source
    }
    T.radius *= 1 - entity.snuggle * 0.16;
    if (entity.remoteK > 0.01) { const w = entity.remoteK * 0.45; T.r += (205 - T.r) * w; T.g += (195 - T.g) * w; T.b += (255 - T.b) * w; T.spin *= 1 + entity.remoteK * 0.8; }
    if (entity.scanK > 0.01) { T.spin *= 1 - entity.scanK * 0.85; T.oscAmp *= 1 - entity.scanK * 0.7; T.dim = Math.min(1, T.dim + 0.1 * entity.scanK); }
    if (entity.glitch > 0.02) T.dim *= 1 - entity.glitch * 0.35;
    T.radius *= 1 - entity.seal * 0.18;
    T.oscFreq *= 1 + entity.load * 0.9; T.oscAmp *= 1 + entity.load * 0.5;

    const k = Math.min(1, dt * 2.5);
    cur.r += (T.r - cur.r) * k; cur.g += (T.g - cur.g) * k; cur.b += (T.b - cur.b) * k;
    for (const key of KEYS) cur[key] += (T[key] - cur[key]) * k;
    const flash = entity.absorb * 0.35 + entity.grow * 0.5 + entity.seal * 0.4;
    const lightT = document.documentElement.dataset.theme === "light";
    const dk = (v) => lightT ? Math.max(0, v * 0.42 - flash * 40) : Math.min(255, v + flash * 70);
    const tint = `${dk(cur.r) | 0},${dk(cur.g) | 0},${dk(cur.b) | 0}`;
    if (((t * 10) | 0) !== entity._orbTick) {
      entity._orbTick = (t * 10) | 0;
      const o = lightT ? [cur.r * 0.55, cur.g * 0.55, cur.b * 0.55] : [cur.r, cur.g, cur.b];
      document.documentElement.style.setProperty("--orb", o.map((v) => v | 0).join(","));
    }

    // ---- cadrage : panneau (coordonnées locales ou écran) → plein écran
    let pv;
    if (entity.flying) {
      const pr = entity.panelRect();
      pv = pr.width > 10
        ? { cx: pr.left + pr.width / 2, cy: pr.top + (pr.height - 24) / 2, s: Math.min(pr.width, pr.height - 30) / (2 * R0 * 1.85), a: 1 }
        : { cx: pr.left + pr.width / 2, cy: pr.top + pr.height / 2, s: 0.04, a: 0 };
    } else pv = { cx: W / 2, cy: (H - 24) / 2, s: Math.min(W, H - 30) / (2 * R0 * 1.85), a: 1 };
    let fv2 = { cx: W / 2, cy: H / 2 - H * 0.04, s: Math.min(W, H) / (2 * R0 * 3.0), a: 1 };
    if (entity.target === "hero" && entity.heroRect) {
      const hr = entity.heroRect();
      if (hr && hr.width > 10) fv2 = { cx: hr.left + hr.width / 2, cy: hr.top + hr.height / 2, s: Math.min(hr.width, hr.height) / (2 * R0 * 1.9), a: 1 };
    }
    const scale = pv.s + (fv2.s - pv.s) * P;
    const vx = pv.cx + (fv2.cx - pv.cx) * P + gaze.x * (1 - P * 0.6);
    const vy = pv.cy + (fv2.cy - pv.cy) * P + gaze.y * (1 - P * 0.6);
    const globalA = pv.a + (1 - pv.a) * Math.min(1, P * 3);
    const sr = stage.getBoundingClientRect();
    entity.screen.x = sr.left + vx; entity.screen.y = sr.top + vy; entity.screen.r = R0 * scale * cur.radius; entity.screen.scale = scale;

    ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.translate(vx, vy);
    ctx.scale(scale, scale);

    const hr = R0 * 2.1 * cur.radius;
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, hr);
    g.addColorStop(0, `rgba(${tint},${(0.09 + flash * 0.25 + P * 0.04 + pw * 0.06) * cur.dim * globalA})`);
    g.addColorStop(1, `rgba(${tint},0)`);
    // (plus d'aura lumineuse autour de la sphère)
    if (false) {   // cœur lumineux désactivé
      const cg = ctx.createRadialGradient(0, 0, 0, 0, 0, R0 * 0.45);
      cg.addColorStop(0, `rgba(${tint},${0.22 * cur.dim * globalA})`); cg.addColorStop(1, `rgba(${tint},0)`);
      ctx.fillStyle = cg; ctx.fillRect(-R0, -R0, R0 * 2, R0 * 2);
    }
    ctx.fillStyle = `rgb(${tint})`;

    const spinSpeed = 0.16 * cur.spin;
    entity.angle = (entity.angle || 0) + dt * spinSpeed;
    const rotY = entity.angle + gaze.x * 0.012, tilt = gaze.y * 0.01;
    const cosR = Math.cos(rotY), sinR = Math.sin(rotY), cosT = Math.cos(tilt), sinT = Math.sin(tilt), fov = 460;
    const breath = entity.night ? 0.7 : 1.1 * (1 + entity.load * 0.8);
    const rad = cur.radius * (1 + Math.sin(t * breath) * 0.016) * (1 - entity.blink * 0.06) * (1 - entity.absorb * 0.1) * (1 + entity.grow * 0.25);
    const oA = cur.oscAmp * 0.75, oF = cur.oscFreq, jit = cur.jitter, sw = cur.swirl, purr = cur.purr;
    const beat = 1 + (Math.pow(Math.abs(Math.sin(t * 3.2)), 6) * 2 - 0.35) * cur.pulse + entity.tokenKick * 0.025 + entity.keyKick * 0.02;
    const sY = cur.stretchY, spk = cur.spike, orbMul = (1 + (cur.radius - 1) * 0.5) * (1 - entity.absorb * 0.2) * (1 - entity.snuggle * 0.25);
    const mx = mouse.x, my = mouse.y, mAct = mouse.active && P < 0.05;
    const attract = pw > 0.3;   // caressée : les fragments viennent vers la main au lieu de fuir
    const rt = entity.rippleT, rippleOn = rt < 1.6, rippleK = rippleOn ? Math.exp(-rt * 2.2) * 26 : 0, front0 = rt * 1.26;
    const spring = Math.min(1, dt * 4), repel = 160 * dt, RR = 2500;
    const pxSize = 1 / scale;
    const visible = 1;
    const ring2 = false;
    const spK = entity.splitK, nSplit = Math.max(2, entity.split || 2), act = entity.activeCluster % nSplit;
    const scK = entity.scanK, band = R0 * 0.13, scanY = Math.sin(t * 1.4) * R0 * 0.95;
    const glJ = entity.glitch * 9, glBand = entity.glitch > 0.05 ? ((t * 23) | 0) % 9 : -1;
    let lastQ = -1;

    const orbStyle = settings.entityStyle === "orb";
    const meshMode = settings.entityStyle !== "fragments" && !orbStyle;
    if (orbStyle) {
      const a = entity.activity;
      const busy = a === "thinking" || a === "talking" || a === "focus" || a === "curious";
      const big = entity.feeding || entity.remoteK > 0.3 || entity.splitK > 0.3 || entity.scan;
      const st = {
        t, dt, R: R0 * rad * 0.82 * (1 + entity.tokenKick * 0.008), px: pxSize, tint, alpha: globalA,
        lit: Math.max(0.1, cur.dim) * Math.min(1, (busy ? 0.8 : 0.2) + entity.tokenKick * 0.5 + (a === "joy" ? 0.4 : 0) + entity.absorb * 0.6 + entity.seal * 0.5) * (a === "sleep" ? 0.25 : 1),
        flow: (a === "sleep" ? 0.15 : busy ? 1.4 : 0.45) * (a === "angry" ? 2.2 : a === "joy" ? 1.3 : 1),
        hueSpread: a === "angry" ? 10 : a === "joy" ? 40 : a === "curious" ? 60 : 28,
        spin: (a === "sleep" ? 0.025 : a === "angry" ? 0.3 : 0.08) * cur.spin * (a === "surprise" ? 2.5 : 1) + gaze.x * 0.002,
        cloudSpeed: a === "angry" ? 2.5 : a === "curious" ? 1.8 : 1.3,
        night: a === "sleep" ? 1.5 : a === "sad" ? 1.2 : 1,
        storm: a === "thinking" || a === "curious" || a === "focus", lightning: a === "angry", rain: a === "sad",
        aurora: Math.max(a === "joy" ? 1 : 0, busy ? 0.6 : 0) * (a === "sleep" ? 0 : 1), open: big,
      };
      orb.step(dt, st);
      orb.draw(ctx, st);
    }
    for (let i = 0; i < (orbStyle ? 0 : N); i++) {
      visA[i] = 0;
      if (rank[i] > visible) continue;
      let tx, ty, tz;
      const ph = phase[i];
      if (isOrb[i]) {
        const a = t * orbSpeed[i] * orbMul * (1 + (cur.spin - 1) * 0.5) + ph, R = orbR[i] * orbMul;
        tx = Math.cos(a) * R; ty = Math.sin(a * 1.3 + ph) * R * 0.3; tz = Math.sin(a) * R;
        if (ring2 && (i & 1)) { const y2 = ty * 0.5 + tz * 0.87, z2 = -ty * 0.87 + tz * 0.5; ty = y2 * 0.9; tz = z2; }   // second anneau incliné
        if (jit) { tx += Math.sin(t * 41 + ph * 17) * jit * 1.5; ty += Math.cos(t * 37 + ph * 11) * jit * 1.5; }
      } else {
        const o1 = Math.sin(t * oF + ph) * oA, o2 = Math.cos(t * oF * 0.83 + ph * 1.7) * oA * 0.7, o3 = Math.sin(t * oF * 1.15 + ph * 2.3) * oA * 0.6;
        let rr = rad * beat * (spk > 0 ? 1 + Math.sin(ph * 5.7) * spk : 1);
        if (purr) rr *= 1 + Math.sin(t * 52 + ph * 9) * 0.008 * purr;
        let rip = 0;
        if (rippleOn) { const d = rN[i] - front0, env = 1 - Math.abs(d) * 3.5; if (env > 0) rip = Math.sin(d * 9) * rippleK * env; }
        let bx = ax[i], bz = az[i];
        if (sw) {   // spirale : chaque latitude tourne à sa vitesse
          const a = sw * Math.sin(t * 0.9 + uy[i] * 3) * 0.9, c = Math.cos(a), s = Math.sin(a);
          const nx = bx * c - bz * s; bz = bx * s + bz * c; bx = nx;
        }
        tx = bx * rr + ux[i] * rip + o1; ty = (ay[i] * rr + uy[i] * rip + o2) * sY; tz = bz * rr + uz[i] * rip + o3;
        if (jit) {   // agitation frénétique
          tx += Math.sin(t * 47 + ph * 13) * jit; ty += Math.cos(t * 43 + ph * 7) * jit; tz += Math.sin(t * 39 + ph * 5) * jit;
        }
        if (spK > 0.01) {   // atelier : amas qui tournent autour d'un centre commun
          const c = i % nSplit, a = t * 0.55 + (c * Math.PI * 2) / nSplit;
          const k2 = 1 - 0.5 * spK;
          tx = tx * k2 + Math.cos(a) * R0 * 1.05 * spK;
          tz = tz * k2 + Math.sin(a) * R0 * 0.7 * spK;
          ty = ty * k2 + Math.sin(a * 2 + c) * R0 * 0.12 * spK;
        }
        if (scK > 0.01) {   // lecture : les fragments se rangent en lignes
          ty += (Math.round(ty / band) * band - ty) * scK;
          tz *= 1 - 0.35 * scK;
        }
        if (glJ > 0.3) {   // perturbation : décalage par bandes
          tx += Math.sin(t * 61 + ph * 19) * glJ;
          if (((ay[i] / R0 * 4.5 + 4.5) | 0) === glBand) tx += glJ * 2.2;
        }
        if (mAct) {
          const dx = px[i] - mx, dy = py[i] - my, d2 = dx * dx + dy * dy;
          if (d2 < RR) {
            const d = Math.sqrt(d2) || 1, f = (1 - d2 / RR) * repel * (attract ? -0.35 : 1);
            px[i] += (dx / d) * f; py[i] += (dy / d) * f;
          }
        }
      }
      px[i] += (tx - px[i]) * spring; py[i] += (ty - py[i]) * spring; pz[i] += (tz - pz[i]) * spring;
      const rx = px[i] * cosR - pz[i] * sinR, rz0 = px[i] * sinR + pz[i] * cosR;
      const ry = py[i] * cosT - rz0 * sinT, rz = py[i] * sinT + rz0 * cosT;
      const sc = fov / (fov + rz);
      if (sc <= 0) continue;
      sxA[i] = rx * sc; syA[i] = ry * sc; szA[i] = rz; visA[i] = 1;
      if (meshMode && (isNode[i] || (isOrb[i] && orbNodes.includes(i)))) continue;   // dessinés avec le maillage
      const backFade = rz > 0 ? 1 - Math.min(0.8, rz / 320) : 1;
      let alpha = (sc * 0.9 > 1 ? 1 : sc * 0.9) * 0.85 * globalA;
      alpha *= isOrb[i] ? 0.45 : depth[i] * cur.dim * backFade;
      alpha *= 0.65 + Math.abs(Math.sin(t * 0.9 + ph * 3)) * 0.35;
      if (scK > 0.01 && !isOrb[i]) { const near = 1 - Math.abs(ry - scanY) / (R0 * 0.16); if (near > 0) alpha = Math.min(1, alpha * (1 + near * 1.6 * scK)); }
      if (spK > 0.3 && !isOrb[i]) alpha *= (i % nSplit) === act ? 1.25 : 0.7;
      if (meshMode) alpha *= isOrb[i] ? 0.6 : 0.42;   // poussière intérieure discrète
      const q = (alpha * 32) | 0;
      if (q !== lastQ) { lastQ = q; ctx.globalAlpha = q / 32; }
      const sz = Math.max(size[i] * sc * pxSize * (1.15 + P * 0.35), pxSize * 0.8);
      ctx.fillRect(rx * sc - sz * 0.5, ry * sc - sz * 0.5, sz, sz);
    }

    // ---- maillage : liens (regroupés par opacité pour aller vite), signaux, nœuds
    if (meshMode) {
      const lw = Math.max(0.55, 0.9 * (1 + P * 0.4)) * pxSize;
      for (let b = 0; b < 10; b++) bucketPaths[b] = null;
      const depthA = (z) => (z > 0 ? 1 - Math.min(0.85, z / 230) : 1);
      for (let e = 0; e < edges.length; e++) {
        const a = edges[e][0], b = edges[e][1];
        if (!visA[a] || !visA[b]) continue;
        let al = 0.5 * cur.dim * globalA * Math.min(depthA(szA[a]), depthA(szA[b]));
        if (spK > 0.05 && (a % nSplit) !== (b % nSplit)) al *= 1 - spK;          // atelier : les amas se détachent
        if (scK > 0.01) { const near = 1 - Math.abs((syA[a] + syA[b]) / 2 - scanY * 0.9) / (R0 * 0.2); if (near > 0) al *= 1 + near * 1.5 * scK; }
        // un lien trop étiré (onde de choc, pointes) s'affine
        const dx = sxA[a] - sxA[b], dy = syA[a] - syA[b], d = Math.sqrt(dx * dx + dy * dy);
        if (d > R0 * 0.9) al *= Math.max(0, 1 - (d - R0 * 0.9) / (R0 * 0.5));
        const k = Math.min(9, (al * 14) | 0);
        if (k <= 0) continue;
        (bucketPaths[k] ||= new Path2D());
        bucketPaths[k].moveTo(sxA[a], syA[a]); bucketPaths[k].lineTo(sxA[b], syA[b]);
      }
      // anneau de nœuds en orbite
      const ringPath = new Path2D();
      for (let k = 0; k < orbNodes.length; k++) {
        const a = orbNodes[k], b = orbNodes[(k + 1) % orbNodes.length];
        if (visA[a] && visA[b] && Math.hypot(sxA[a] - sxA[b], syA[a] - syA[b]) < R0 * 0.55) { ringPath.moveTo(sxA[a], syA[a]); ringPath.lineTo(sxA[b], syA[b]); }
      }
      ctx.strokeStyle = `rgb(${tint})`; ctx.lineWidth = lw; ctx.lineCap = "round";
      for (let k = 1; k < 10; k++) if (bucketPaths[k]) { ctx.globalAlpha = k / 14; ctx.stroke(bucketPaths[k]); }
      ctx.globalAlpha = 0.16 * globalA * cur.dim; ctx.stroke(ringPath);

      // signaux : plus nombreux quand Atom réfléchit, parle, cherche ou consulte une autre IA
      const busyAct = entity.activity === "thinking" || entity.activity === "talking" || entity.activity === "curious";
      const rate = 1 + (busyAct ? 7 : 0) + entity.tokenKick * 26 + entity.workK * 22;
      sigAcc += dt * rate;
      while (sigAcc >= 1) {
        sigAcc -= 1;
        for (let k = 0; k < SIG; k++) if (sgE[k] < 0) { sgE[k] = (Math.random() * edges.length) | 0; sgT[k] = 0; sgV[k] = 1.2 + Math.random() * 1.6; break; }
      }
      const wc = entity.workC || [255, 255, 255], wk = entity.workK || 0;
      ctx.fillStyle = wk > 0.3 ? `rgb(${lightT ? wc.map((v) => (v * 0.5) | 0).join(",") : wc.join(",")})` : lightT ? "#111" : "#fff";
      for (let k = 0; k < SIG; k++) {
        if (sgE[k] < 0) continue;
        sgT[k] += dt * sgV[k];
        if (sgT[k] >= 1) {   // le signal continue parfois vers un lien voisin
          const [, b] = edges[sgE[k]];
          if (Math.random() < 0.55) {
            const next = edges.findIndex((ed, n) => n !== sgE[k] && (ed[0] === b || ed[1] === b));
            if (next >= 0) { if (edges[next][1] === b) edges[next] = [edges[next][1], edges[next][0]]; sgE[k] = next; sgT[k] = 0; continue; }
          }
          sgE[k] = -1; continue;
        }
        const [a, b] = edges[sgE[k]];
        if (!visA[a] || !visA[b]) { sgE[k] = -1; continue; }
        const u = sgT[k], x = sxA[a] + (sxA[b] - sxA[a]) * u, y = syA[a] + (syA[b] - syA[a]) * u;
        const z = szA[a] + (szA[b] - szA[a]) * u;
        const al = Math.sin(u * Math.PI) * globalA * (z > 0 ? 0.35 : 0.95);
        const big = 1 + wk * 0.8;   // signaux plus gros pendant un travail long
        ctx.globalAlpha = al * 0.25; ctx.beginPath(); ctx.arc(x, y, 3.2 * pxSize * big, 0, 6.283); ctx.fill();
        ctx.globalAlpha = al; ctx.fillRect(x - pxSize * big, y - pxSize * big, pxSize * 2 * big, pxSize * 2 * big);
      }

      // nœuds : petits disques, plus gros et nets à l'avant
      ctx.fillStyle = `rgb(${tint})`;
      const drawNode = (i, base) => {
        if (!visA[i]) return;
        const z = szA[i], f = z > 0 ? 1 - Math.min(0.8, z / 260) : 1;
        let al = base * f * cur.dim * globalA;
        if (spK > 0.3) al *= (i % nSplit) === act ? 1.2 : 0.7;
        ctx.globalAlpha = Math.min(1, al);
        const r = (0.7 + 1.1 * f) * pxSize * (1 + P * 0.3);
        ctx.beginPath(); ctx.arc(sxA[i], syA[i], r, 0, 6.283); ctx.fill();
      };
      for (const i of nodeIdx) drawNode(i, 0.95);
      for (const i of orbNodes) drawNode(i, 0.6);
    }

    // ---- nourriture : fragments bleus attirés vers la sphère
    ctx.fillStyle = `rgb(${entity.feedColor.join(",")})`;
    let alive = 0;
    for (let i = 0; i < F; i++) {
      if (!fa[i]) continue;   // (fragments « nourriture » retirés : le travail passe par les signaux)
      alive++;
      const d = Math.hypot(fx[i], fy[i]) || 1;
      fv[i] += dt * 90;
      const step = Math.min(d, fv[i] * dt);
      fx[i] -= (fx[i] / d) * step; fy[i] -= (fy[i] / d) * step;
      // légère courbe pour un mouvement organique
      fx[i] += (-fy[i] / d) * dt * 18; fy[i] += (fx[i] / d) * dt * 18;
      if (d < R0 * 0.85) { fa[i] = 0; entity.tokenKick = Math.min(1, entity.tokenKick + 0.15); continue; }
      ctx.globalAlpha = Math.min(1, (R0 * 4.2 - d) / (R0 * 1.2)) * 0.9 * globalA;
      const sz = fs[i] * pxSize * 1.6;
      ctx.fillRect(fx[i] - sz / 2, fy[i] - sz / 2, sz, sz);
      ctx.globalAlpha *= 0.35;
      ctx.fillRect(fx[i] + (fx[i] / d) * 6 - sz / 2, fy[i] + (fy[i] / d) * 6 - sz / 2, sz, sz);
    }

    // ---- IA distante : ondes de fragments qui partent de la sphère vers l'extérieur
    if (entity.remoteK > 0.02) {
      ctx.fillStyle = "rgb(205,195,255)";
      for (let w = 0; w < 3; w++) {
        const ph = (t * 0.55 + w / 3) % 1, rr = R0 * (1.15 + ph * 2.4);
        const n = 90, a0 = t * 0.3 + w;
        ctx.globalAlpha = Math.min(1, (1 - ph) * 1.1) * entity.remoteK * globalA;
        for (let j = 0; j < n; j++) {
          const a = a0 + (j / n) * Math.PI * 2;
          const sz = pxSize * (2.6 - ph * 1.2);
          ctx.fillRect(Math.cos(a) * rr - sz / 2, Math.sin(a) * rr * 0.34 - sz / 2, sz, sz);
        }
      }
    }
    // ---- sauvegarde : un anneau se referme autour de la sphère
    if (entity.seal > 0.03) {
      ctx.strokeStyle = `rgba(${tint},${entity.seal * 0.8 * globalA})`;
      ctx.lineWidth = pxSize * 1.5;
      ctx.beginPath();
      ctx.ellipse(0, 0, R0 * (1.25 + entity.seal * 0.9), R0 * (1.25 + entity.seal * 0.9) * 0.36, 0, 0, Math.PI * 2 * (1 - entity.seal * 0.7));
      ctx.stroke();
    }
    ctx.restore();
  }
  requestAnimationFrame(frame);
})();

/* Signal : de l'entité vers un élément de l'interface (source citée, souvenir utilisé). */
function signalTo(el, delay = 0) {
  if (!el) return;
  setTimeout(() => {
    const r = el.getBoundingClientRect();
    const sx = entity.screen.x, sy = entity.screen.y;
    if (!sx && !sy || !r.width) return;
    const tx = r.left + 14, ty = r.top + r.height / 2;
    const dot = document.createElement("div");
    dot.className = "sigfrag"; dot.style.left = sx + "px"; dot.style.top = sy + "px";
    document.body.appendChild(dot);
    const dx = tx - sx, dy = ty - sy;
    entity.tokenKick = 1;
    dot.animate([
      { transform: "translate(-50%,-50%) scale(.6)", opacity: 0 },
      { transform: `translate(calc(-50% + ${dx * 0.5}px), calc(-50% + ${dy * 0.5 - 40}px)) scale(1.2)`, opacity: 1, offset: 0.5 },
      { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(.8)`, opacity: 1 },
    ], { duration: 850, easing: "cubic-bezier(.4,0,.2,1)" }).onfinish = () => {
      dot.remove(); el.classList.remove("lit"); void el.offsetWidth; el.classList.add("lit");
    };
  }, delay);
}

/* Un souvenir retenu : un fragment lumineux part du message et entre dans la sphère. */
function memoryFlight(fromEl) {
  return;   // animation retirée (entité plus sobre) — le souvenir s'affiche en carte sous la réponse

  const r = (fromEl || $("chat")).getBoundingClientRect();
  const sx = r.left + Math.min(40, r.width / 2), sy = r.top + Math.min(20, r.height / 2);
  const tx = entity.screen.x, ty = entity.screen.y;
  if (!tx && !ty) { entity.absorb = 1; return; }
  const dot = document.createElement("div");
  dot.className = "memfrag";
  dot.style.left = sx + "px"; dot.style.top = sy + "px";
  document.body.appendChild(dot);
  const dx = tx - sx, dy = ty - sy;
  const anim = dot.animate([
    { transform: "translate(-50%,-50%) scale(.4)", opacity: 0 },
    { transform: `translate(calc(-50% + ${dx * 0.25}px), calc(-50% + ${dy * 0.1 - 60}px)) scale(1.4)`, opacity: 1, offset: 0.3 },
    { transform: `translate(calc(-50% + ${dx * 0.8}px), calc(-50% + ${dy * 0.75}px)) scale(1)`, opacity: 1, offset: 0.85 },
    { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(.3)`, opacity: 0.2 },
  ], { duration: 1300, easing: "cubic-bezier(.45,.05,.3,1)" });
  anim.onfinish = () => { dot.remove(); entity.absorb = 1; entity.rippleT = 0.6; };
}

/* ============================================================
   OUTILS
   ============================================================ */
const $ = (id) => document.getElementById(id);
const store = {
  get(k, d) { try { const v = localStorage.getItem("atom." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("atom." + k, JSON.stringify(v)); } catch {} },
};
const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const DEFAULT_PERSONA =
  "Tu es Atom, une entité numérique bienveillante, curieuse et concise. " +
  "Tu parles français avec naturel et chaleur.";
const settings = Object.assign(
  { model: "", persona: DEFAULT_PERSONA, autoMemory: true, conversationId: null, side: true, panel: true },
  store.get("settings", {})
);
const saveSettings = () => store.set("settings", settings);

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", "X-Atom": "1", ...(opts.headers || {}) } });
  if (!r.ok) {
    let j = {};
    try { j = await r.json(); } catch {}
    if (r.status === 401 && j.auth) showLogin(false);
    throw new Error(j.detail || `${path} → ${r.status}`);
  }
  return r;
}
const getJSON = async (p) => (await api(p)).json();
const send_ = (p, method, body) => api(p, { method, body: body ? JSON.stringify(body) : undefined });

let toastTimer = 0;
function toast(html) {
  const t = $("toast");
  t.innerHTML = html;
  t.classList.add("on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("on"), 4500);
}
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch {}
    ta.remove();
  }
}
const fmtTime = (ts) => new Date(ts * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
function fmtBytes(b) { if (!b) return "0"; const u = ["o", "Ko", "Mo", "Go", "To"]; let i = 0; while (b >= 1024 && i < 4) { b /= 1024; i++; } return b.toFixed(i >= 3 ? 1 : 0) + " " + u[i]; }
function fmtDur(s) { if (s == null) return "—"; const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return d ? `${d} j ${h} h` : h ? `${h} h ${m} min` : `${m} min`; }

/* ============================================================
   MARKDOWN — rendu minimal et sûr
   ============================================================ */
function inline(t) {
  const codes = [];
  t = t.replace(/`([^`\n]+)`/g, (_, c) => (codes.push(c), `\u0000${codes.length - 1}\u0000`));
  t = esc(t)
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/(^|[^\w])_([^_\n]+)_(?!\w)/g, "$1<em>$2</em>")
    .replace(/~~([^~\n]+)~~/g, "<del>$1</del>")
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<]*[^\s<.,;:!?)\]'"])/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
  return t.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[+i])}</code>`);
}

/* coloration syntaxique minimale, en niveaux de gris */
const KW = new Set(("if else elif for while do return function def class import from export default const let var new " +
  "try except catch finally raise throw with as in of is not and or async await yield lambda pass break continue " +
  "switch case public private static void int float str bool true false null none None True False self this fn pub " +
  "struct impl use match select where insert update delete create table into values echo then fi done").split(" "));
function highlight(code) {
  const re = /(\/\/[^\n]*|#[^\n]*|\/\*[\s\S]*?\*\/|--[^\n]*)|("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)|\b(\d+(?:\.\d+)?)\b|\b([A-Za-z_]\w*)(?=\s*\()|\b([A-Za-z_]\w*)\b/g;
  let out = "", last = 0, m;
  while ((m = re.exec(code))) {
    out += esc(code.slice(last, m.index));
    const [tok, com, str, num, fn, word] = m;
    if (com) out += `<span class="tk-c">${esc(com)}</span>`;
    else if (str) out += `<span class="tk-s">${esc(str)}</span>`;
    else if (num) out += `<span class="tk-n">${num}</span>`;
    else if (fn) out += KW.has(fn) ? `<span class="tk-k">${fn}</span>` : `<span class="tk-f">${fn}</span>`;
    else out += KW.has(word) ? `<span class="tk-k">${word}</span>` : esc(word);
    last = m.index + tok.length;
  }
  return out + esc(code.slice(last));
}

/* formules : protégées avant le Markdown, rendues ensuite par KaTeX (chargé à la demande) */
let mathStore = [];
function protectMath(src) {
  if (!/\$|\\\(|\\\[/.test(src)) return src;
  const parts = src.split(/(^\s*```[\s\S]*?^\s*```)/m);
  return parts.map((seg, i) => i % 2 ? seg : seg
    .replace(/\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]/g, (_, a, b) => { mathStore.push({ tex: a ?? b, block: true }); return `\u0001${mathStore.length - 1}\u0001`; })
    .replace(/\\\((.+?)\\\)|\$(?!\s)([^$\n]*?[A-Za-z\\^_{}][^$\n]*?)(?<!\s)\$/g, (_, a, b) => { mathStore.push({ tex: a ?? b, block: false }); return `\u0001${mathStore.length - 1}\u0001`; })
  ).join("");
}
function restoreMath(html) {
  return html.replace(/\u0001(\d+)\u0001/g, (_, i) => {
    const m = mathStore[+i];
    return m ? `<span class="math${m.block ? " math-block" : ""}" data-tex="${esc(m.tex)}">${esc(m.tex)}</span>` : "";
  });
}
let katexLoading = null;
function loadKatex() {
  if (window.katex) return Promise.resolve();
  if (katexLoading) return katexLoading;
  katexLoading = new Promise((res, rej) => {
    const l = document.createElement("link");
    l.rel = "stylesheet"; l.href = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css";
    document.head.appendChild(l);
    const sc = document.createElement("script");
    sc.src = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js";
    sc.onload = res; sc.onerror = rej;
    document.head.appendChild(sc);
  });
  return katexLoading;
}
function renderMath(el) {
  renderMermaid(el);
  const nodes = el.querySelectorAll(".math[data-tex]");
  if (!nodes.length) return;
  loadKatex().then(() => nodes.forEach((n) => {
    try { window.katex.render(n.dataset.tex, n, { displayMode: n.classList.contains("math-block"), throwOnError: false }); n.removeAttribute("data-tex"); } catch {}
  })).catch(() => {});
}
function setMd(el, text) { el.innerHTML = md(text); renderMath(el); }
// Schémas Mermaid : chargés à la demande, rendus en monochrome selon le thème.
let mermaidLoading = null, mmSeq = 0;
function loadMermaid() {
  if (window.mermaid) return Promise.resolve();
  if (mermaidLoading) return mermaidLoading;
  mermaidLoading = new Promise((res, rej) => {
    const sc = document.createElement("script");
    sc.src = "https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js";
    sc.onload = () => res(); sc.onerror = rej; document.head.appendChild(sc);
  });
  return mermaidLoading;
}
function renderMermaid(el) {
  const nodes = [...el.querySelectorAll(".mm[data-src]")];
  if (!nodes.length) return;
  loadMermaid().then(async () => {
    const light = document.documentElement.dataset.theme === "light";
    window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base", fontFamily: getComputedStyle(document.body).fontFamily,
      themeVariables: light ? { primaryColor: "#f1f1ee", primaryBorderColor: "#9a9a96", primaryTextColor: "#1b1b1b", lineColor: "#8a8a86", fontSize: "13px" }
        : { primaryColor: "#262626", primaryBorderColor: "#4a4a4a", primaryTextColor: "#e6e6e6", lineColor: "#6a6a6a", secondaryColor: "#222", tertiaryColor: "#1e1e1e", background: "#1b1b1b", fontSize: "13px" } });
    for (const n of nodes) {
      const src = n.dataset.src; n.removeAttribute("data-src");
      try { const { svg } = await window.mermaid.render("mm" + (++mmSeq), src); n.innerHTML = svg; n.dataset.code = src; }
      catch { n.innerHTML = `<pre class="mm-wait">${esc(src)}</pre><p class="note">Schéma illisible : voici son code.</p>`; }
    }
  }).catch(() => {});
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-mmcode], [data-mmsvg]"); if (!b) return;
  const box = b.closest(".mm-box"), mm = box.querySelector(".mm");
  if (b.hasAttribute("data-mmcode")) { copyText(mm.dataset.code || mm.textContent); toast("Code du schéma copié."); }
  else { const svg = mm.querySelector("svg"); if (!svg) return; const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([svg.outerHTML], { type: "image/svg+xml" })); a.download = "schema.svg"; a.click(); }
});
const isRow = (l) => /^\s*\|.*\|\s*$/.test(l);
const isSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
const cells = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());

function md(src) {
  mathStore = [];
  return restoreMath(mdRaw(protectMath(src)));
}
function mdRaw(src) {
  const lines = src.replace(/\r/g, "").split("\n");
  let out = "", i = 0, para = [];
  const flush = () => { if (para.length) { out += `<p>${para.map(inline).join("<br>")}</p>`; para = []; } };
  while (i < lines.length) {
    const l = lines[i];
    let m;
    if ((m = l.match(/^\s*```\s*([\w+#.-]*)/))) {
      flush();
      const buf = [];
      i++;
      while (i < lines.length && !/^\s*```/.test(lines[i])) buf.push(lines[i++]);
      i++;
      if ((m[1] || "").toLowerCase() === "mermaid") {
        out += `<div class="mm-box"><div class="mm" data-src="${esc(buf.join("\n"))}"><pre class="mm-wait">${esc(buf.join("\n"))}</pre></div><div class="mm-acts"><button data-mmcode>Voir le code</button><button data-mmsvg>Télécharger (SVG)</button></div></div>`;
      } else
      out += `<div class="code"><div class="code-h"><span>${esc(m[1] || "code")}</span><button data-copy>${icon("copy")}Copier</button></div><pre><code>${highlight(buf.join("\n"))}</code></pre></div>`;
      continue;
    }
    if (isRow(l) && i + 1 < lines.length && isSep(lines[i + 1])) {
      flush();
      const head = cells(l);
      i += 2;
      let body = "";
      while (i < lines.length && isRow(lines[i])) { body += "<tr>" + cells(lines[i]).map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>"; i++; }
      out += `<div class="tbl"><table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>`;
      continue;
    }
    if ((m = l.match(/^\s*(#{1,4})\s+(.*)$/))) { flush(); out += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; i++; continue; }
    if (/^\s*([-*_])\s*\1\s*\1[\s\1]*$/.test(l)) { flush(); out += "<hr>"; i++; continue; }
    if (/^\s*>/.test(l)) {
      flush();
      const buf = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
      out += `<blockquote>${mdRaw(buf.join("\n"))}</blockquote>`;
      continue;
    }
    if ((m = l.match(/^\s*([-*+]|\d+[.)])\s+/))) {
      flush();
      const ordered = /\d/.test(m[1]);
      let items = "";
      while (i < lines.length && (m = lines[i].match(/^\s*([-*+]|\d+[.)])\s+(.*)$/)) && /\d/.test(m[1]) === ordered) {
        let item = m[2];
        i++;
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) item += " " + lines[i++].trim();
        items += `<li>${inline(item)}</li>`;
      }
      out += ordered ? `<ol>${items}</ol>` : `<ul>${items}</ul>`;
      continue;
    }
    if (!l.trim()) { flush(); i++; continue; }
    para.push(l); i++;
  }
  flush();
  return out;
}

/* ============================================================
   MISE EN PAGE (barre latérale, panneau)
   ============================================================ */
const app = $("app");
const narrow = () => matchMedia("(max-width: 760px)").matches;
const medium = () => matchMedia("(max-width: 1180px)").matches;

// En mode Code, le panneau de l'entité est replié par défaut (réglage séparé) pour laisser la place au code.
const panelKey = () => (app.dataset.view === "code" ? "panelCode" : "panel");
function applyLayout() {
  const on = app.dataset.view === "code" ? !!settings.panelCode : settings.panel;
  app.classList.toggle("no-side", !settings.side);
  app.classList.toggle("no-panel", !on);
  $("sideOpen").style.display = (!settings.side || narrow()) ? "" : "none";
  $("panelBtn").classList.toggle("on", medium() ? app.classList.contains("panel-open") : on);
}
$("sideClose").onclick = () => { if (narrow()) app.classList.remove("side-open"); else { settings.side = false; saveSettings(); applyLayout(); } };
$("sideOpen").onclick = () => { if (narrow()) app.classList.add("side-open"); else { settings.side = true; saveSettings(); applyLayout(); } };
$("panelBtn").onclick = () => {
  if (medium()) app.classList.toggle("panel-open");
  else { settings[panelKey()] = !(app.dataset.view === "code" ? settings.panelCode : settings.panel); saveSettings(); }
  applyLayout();
  refreshPanel();
  refreshSystem();
};
$("panelClose").onclick = () => { if (medium()) app.classList.remove("panel-open"); else { settings[panelKey()] = false; saveSettings(); } applyLayout(); };
$("scrim").onclick = () => { app.classList.remove("side-open", "panel-open"); applyLayout(); };
addEventListener("resize", applyLayout);
const panelVisible = () => medium() ? app.classList.contains("panel-open") : (app.dataset.view === "code" ? !!settings.panelCode : settings.panel);

/* ============================================================
   CONVERSATIONS
   ============================================================ */
let history = [];
let conversations = [];

function groupOf(ts) {
  const d = new Date(ts * 1000), now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = (day(now) - day(d)) / 86400000;
  if (diff < 1) return "Aujourd'hui";
  if (diff < 2) return "Hier";
  if (diff < 7) return "7 derniers jours";
  if (diff < 30) return "30 derniers jours";
  return "Plus ancien";
}

async function loadConversations() {
  try { conversations = (await getJSON("/api/conversations")).conversations; } catch (e) { console.warn(e); }
  if (!$("search").value.trim()) renderConversations(conversations);
  updateTitle();
}

function convItem(c, snippet) {
  const el = document.createElement("div");
  el.className = "conv" + (c.id === settings.conversationId ? " active" : "");
  const t = document.createElement("div");
  t.className = "t"; t.title = c.title;
  t.textContent = c.title;
  if (c.space_id && !(typeof activeSpace === "function" && activeSpace())) {
    const sp = (typeof spacesList !== "undefined" ? spacesList : []).find((x) => x.id === c.space_id);
    if (sp) { const g = document.createElement("span"); g.className = "sp-tag"; g.textContent = sp.name; t.appendChild(g); }
  }
  if (snippet) { const s = document.createElement("span"); s.className = "snip"; s.textContent = snippet; t.appendChild(s); }
  t.onclick = () => { openConversation(c.id); app.classList.remove("side-open"); };
  t.ondblclick = () => renameInline(el, c);
  const pin = document.createElement("button");
  pin.className = "iconbtn a"; pin.title = c.pinned ? "Désépingler" : "Épingler"; pin.innerHTML = icon("pin");
  if (c.pinned) pin.style.color = "var(--text)";
  pin.onclick = async (e) => { e.stopPropagation(); await send_(`/api/conversations/${c.id}`, "PATCH", { pinned: !c.pinned }); loadConversations(); };
  const del = document.createElement("button");
  del.className = "iconbtn a"; del.title = "Supprimer"; del.innerHTML = icon("trash");
  del.onclick = async (e) => {
    e.stopPropagation();
    if (!confirm(`Supprimer « ${c.title} » ?`)) return;
    await send_(`/api/conversations/${c.id}`, "DELETE");
    if (c.id === settings.conversationId) newConversation();
    loadConversations();
  };
  el.append(t, pin, del);
  return el;
}

let convAnimated = false;
function renderConversations(list, search = false) {
  const sp = typeof activeSpace === "function" ? activeSpace() : null;
  if (sp && !search) list = list.filter((c) => c.space_id === sp.id);
  const nav = $("convList");
  nav.innerHTML = "";
  const animate = !convAnimated || search; convAnimated = true;
  let k = 0;
  const _append = nav.appendChild.bind(nav);
  nav.appendChild = (el) => { if (animate && el.classList?.contains("conv")) { el.classList.add("in"); el.style.setProperty("--i", k++); } return _append(el); };
  if (!list.length) {
    nav.innerHTML = `<div class="side-empty">${search ? "Aucun résultat." : sp ? "Aucune conversation dans cet espace : écris un message pour commencer." : "Aucune conversation pour l'instant."}</div>`;
    return;
  }
  if (search) {
    for (const c of list) nav.appendChild(convItem(c, c.snippet ? c.snippet.slice(0, 80) : ""));
    return;
  }
  const pinned = list.filter((c) => c.pinned);
  const groups = new Map();
  if (pinned.length) groups.set("Épinglées", pinned);
  for (const c of list.filter((c) => !c.pinned)) {
    const g = groupOf(c.updated_at);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(c);
  }
  for (const [name, items] of groups) {
    const h = document.createElement("div"); h.className = "group"; h.textContent = name;
    nav.appendChild(h);
    for (const c of items) nav.appendChild(convItem(c));
  }
}

function renameInline(el, c) {
  const inp = document.createElement("input");
  inp.value = c.title;
  el.innerHTML = ""; el.appendChild(inp); inp.focus(); inp.select();
  const done = async (save) => {
    const v = inp.value.trim();
    if (save && v && v !== c.title) await send_(`/api/conversations/${c.id}`, "PATCH", { title: v });
    loadConversations();
  };
  inp.onkeydown = (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); };
  inp.onblur = () => done(true);
}

let searchTimer = 0;
$("palKbd").onclick = (e) => { e.preventDefault(); openPalette(); };
$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = $("search").value.trim();
  if (q.length < 2) { renderConversations(conversations); return; }
  searchTimer = setTimeout(async () => {
    try { renderConversations((await getJSON("/api/search?q=" + encodeURIComponent(q))).results, true); } catch {}
  }, 200);
});

function currentConv() { return conversations.find((c) => c.id === settings.conversationId); }
function updateTitle() {
  if (typeof currentView !== "undefined" && currentView !== "chat") { $("title").textContent = currentView === "code" ? "Code" : "Bibliothèque"; return; }
  const c = currentConv();
  $("title").textContent = c ? c.title : "Nouvelle conversation";
  $("pinBtn").style.display = c ? "" : "none";
  $("exportBtn").style.display = c ? "" : "none";
  $("pinBtn").classList.toggle("on", !!(c && c.pinned));
  $("pinBtn").title = c && c.pinned ? "Désépingler" : "Épingler";
  document.title = c ? `${c.title} · Atom` : "Atom";
}
$("title").onclick = () => {
  const c = currentConv();
  if (!c) return;
  const inp = document.createElement("input");
  inp.className = "title-input"; inp.value = c.title;
  $("title").replaceWith(inp); inp.focus(); inp.select();
  const done = async (save) => {
    const v = inp.value.trim();
    inp.replaceWith(titleBtn);
    if (save && v && v !== c.title) await send_(`/api/conversations/${c.id}`, "PATCH", { title: v });
    loadConversations();
  };
  inp.onkeydown = (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); };
  inp.onblur = () => done(true);
};
const titleBtn = $("title");
$("pinBtn").onclick = async () => {
  const c = currentConv(); if (!c) return;
  await send_(`/api/conversations/${c.id}`, "PATCH", { pinned: !c.pinned });
  loadConversations();
};
$("exportBtn").onclick = () => {
  const c = currentConv(); if (!c) return;
  let out = `# ${c.title}\n\n`;
  for (const m of history) {
    const who = m.role === "user" ? "**Moi**" : "**Atom**";
    const when = m.created_at ? ` · ${new Date(m.created_at * 1000).toLocaleString("fr-FR")}` : "";
    out += `${who}${when}\n\n${m.content}\n\n---\n\n`;
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([out], { type: "text/markdown" }));
  a.download = (c.title.replace(/[\\/:*?"<>|]+/g, "").slice(0, 60) || "conversation") + ".md";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};

async function openConversation(id) {
  if (busy) return;
  if (currentView !== "chat") showView("chat");
  try {
    history = (await getJSON(`/api/conversations/${id}/messages`)).messages;
    settings.conversationId = id;
  } catch { history = []; settings.conversationId = null; }
  saveSettings();
  restoreDraft();
  const c = conversations.find((x) => x.id === id);
  if (c?.model && [...modelSel.options].some((o) => o.value === c.model)) modelSel.value = c.model;
  else modelSel.value = settings.model;
  renderHistory();
  renderConversations(conversations);
  updateTitle();
  input.focus();
}

function newConversation() {
  if (busy) return;
  if (currentView !== "chat") showView("chat");
  settings.conversationId = null;
  saveSettings();
  history = [];
  restoreDraft();
  modelSel.value = settings.model;
  renderHistory();
  renderConversations(conversations);
  updateTitle();
  setEmotion("idle");
  app.classList.remove("side-open");
  input.focus();
}
$("newConv").onclick = newConversation;

/* ============================================================
   MESSAGES
   ============================================================ */
const chat = $("chat"), scroller = $("scroller"), input = $("input"), sendBtn = $("send"), form = $("form");

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Bonne nuit." : h < 12 ? "Bonjour." : h < 18 ? "Bon après-midi." : "Bonsoir.";
}
// Suggestions d'accueil adaptées à ce qui est configuré (bibliothèque, projets, recherche web).
const BASE_SUGGESTIONS = [
  { i: "clock", t: "Programmer un rappel", d: "« Rappelle-moi demain à 9 h de… »", fill: "Rappelle-moi demain à 9 h de " },
  { i: "doc", t: "Rédiger un texte", d: "Mail, message, résumé…", fill: "Rédige un mail court pour " },
  { i: "user", t: "Ce que tu sais de moi", d: "Voir ce qu'Atom a retenu", send: "Qu'est-ce que tu sais de moi ?" },
  { i: "scale", t: "Comparer deux options", d: "Un tableau clair des avantages", fill: "Compare dans un tableau " },
];
function suggestions() {
  const cols = (typeof library !== "undefined" && library?.collections) || [];
  const ready = cols.filter((c) => c.status !== "error" && c.chunks > 0);
  const docs = ready.filter((c) => c.kind !== "code"), code = ready.filter((c) => c.kind === "code");
  const out = [];
  if (docs.length) {
    const c = docs[Math.floor(Math.random() * docs.length)];
    out.push({ i: "library", t: "Interroger ta bibliothèque", d: `Dans « ${c.name} »`, fill: "D'après mes documents, ", scope: String(c.id) });
  }
  if (code.length) {
    const c = code[Math.floor(Math.random() * code.length)];
    out.push({ i: "code", t: `Explique ${c.name}`, d: "Architecture et fichiers clés", send: `Explique-moi l'architecture du projet ${c.name} : rôle des dossiers et fichiers principaux.`, scope: String(c.id) });
  }
  if (typeof searchAvailable !== "undefined" && searchAvailable)
    out.push({ i: "globe", t: "Chercher sur Internet", d: "Actualité, prix, horaires…", fill: "Cherche sur Internet ", web: true });
  for (const s of BASE_SUGGESTIONS) if (out.length < 4) out.push(s);
  return out;
}

function renderCards() {
  const cards = chat.querySelector("#empty .cards");
  if (!cards) return;
  cards.innerHTML = "";
  suggestions().forEach((s, k) => {
    const b = document.createElement("button");
    b.className = "card"; b.style.setProperty("--i", k);
    if (s.scope || s.web) b.dataset.cap = 1;
    b.innerHTML = `<b>${icon(s.i)}${esc(s.t)}</b><span>${esc(s.d)}</span>`;
    b.onclick = () => {
      if (s.scope) setScope(s.scope);
      if (s.web) { webForce = true; renderWebBtn(); }
      s.send ? sendMessage(s.send) : fillInput(s.fill);
    };
    cards.appendChild(b);
  });
}

function renderEmpty() {
  const g = greeting().replace(/\.$/, "");
  chat.innerHTML = `<div id="empty"><div id="heroSlot"></div><h1><span class="orbtxt">${g}</span>.</h1><p>Que puis-je faire pour toi ?</p><div class="today" id="today"></div><div class="cards"></div></div>`;
  renderCards();
  renderToday();
  requestAnimationFrame(() => enterHero());
}

function fillInput(text) { input.value = text; autoGrow(); input.focus(); input.setSelectionRange(text.length, text.length); }

function msgEl(m, idx, fresh = false) {
  const el = document.createElement("div");
  const isUser = m.role === "user";
  el.className = "msg " + (m.error ? "err" : isUser ? "user" : "atom") + (fresh ? " fresh" : "");
  el.dataset.idx = idx;
  const files = m.meta?.attachments;
  if (isUser && files?.length) {
    const f = document.createElement("div");
    f.className = "files";
    for (const a of files) f.appendChild(fileChip(a));
    el.appendChild(f);
  }
  const body = document.createElement("div");
  body.className = "body" + (isUser ? "" : " md");
  if (isUser || m.error) body.textContent = m.content; else setMd(body, m.content);
  if (isUser && !m.content) body.style.display = "none";
  el.appendChild(body);
  if (!isUser && m.meta?.workshop) el.insertBefore(workshopEl(m.meta.workshop), body);
  if (!isUser && m.meta?.docs?.length) el.appendChild(docsEl(m.meta.docs));
  if (!isUser && m.meta?.reminders?.length) for (const r of m.meta.reminders) el.appendChild(reminderCard(r));
  if (!isUser && m.meta?.analysis) el.appendChild(analysisEl(m.meta.analysis));
  if (!isUser && m.meta?.research) body.insertAdjacentHTML("beforebegin", `<div class="rs-tag">${icon("library")}Recherche approfondie · ${m.meta.research.queries?.length || 0} recherches · ${m.meta.sources?.length || 0} sources${m.meta.research.engine ? ` · ${esc(m.meta.research.engine)}` : ""}</div>`);
  if (!isUser && m.meta?.sources?.length) el.appendChild(sourcesEl(m.meta.sources));
  if (!isUser && m.meta?.used) el.appendChild(usedEl(m.meta.used));
  if (!m.error) el.appendChild(actions(m, idx));
  return el;
}

function fileChip(a, onRemove) {
  const c = document.createElement("span");
  c.className = "file" + (a.loading ? " loading" : "");
  const size = a.loading ? "lecture…" : a.data ? "analyse Python" : a.pages ? `${a.pages} p.` : `${Math.max(1, Math.round((a.chars ?? a.text?.length ?? 0) / 1000))} k car.`;
  c.innerHTML = `${icon("doc")}<b>${esc(a.name)}</b><small>${size}</small>`;
  if (onRemove) {
    const x = document.createElement("button");
    x.type = "button"; x.title = "Retirer"; x.innerHTML = icon("x");
    x.onclick = onRemove;
    c.appendChild(x);
  }
  return c;
}

function sourcesEl(list) {
  const d = document.createElement("div");
  d.className = "src-cards sources";
  list.slice(0, 6).forEach((x, i) => {
    const a = document.createElement("a");
    a.className = "src-card src-l"; a.href = x.url; a.target = "_blank"; a.rel = "noopener noreferrer"; a.title = x.title;
    a.innerHTML = `<div class="d"><i>${i + 1}</i>${esc(x.domain)}</div><b>${esc(x.title)}</b>${x.snippet ? `<p>${esc(x.snippet)}</p>` : ""}`;
    d.appendChild(a);
  });
  return d;
}

/* Carte de rappel dans le fil : date, texte, annulation */
let pendingReminders = null;
async function pendingIds() {
  if (!pendingReminders) pendingReminders = getJSON("/api/reminders").then((r) => new Set(r.reminders.map((x) => x.id))).catch(() => new Set());
  return pendingReminders;
}
function reminderCard(r) {
  const c = document.createElement("div");
  c.className = "acard";
  const cancelled = r.action === "cancelled";
  c.innerHTML = `<span class="ic">${icon("clock")}</span><div class="tx"><b>${esc(cancelled ? `Rappel #${r.id} annulé` : r.text || "Rappel")}</b><small>${esc(cancelled ? "" : r.when || "")}</small></div>`;
  if (!cancelled) {
    const b = document.createElement("button"); b.className = "btn sm"; b.textContent = "Annuler";
    b.onclick = async () => {
      try { await send_(`/api/reminders/${r.id}`, "DELETE"); } catch { toast("Ce rappel a déjà été envoyé ou annulé."); }
      pendingReminders = null; c.classList.add("done"); b.remove(); c.querySelector("small").textContent = "annulé"; refreshPanel();
    };
    c.appendChild(b);
    pendingIds().then((ids) => { if (!ids.has(r.id)) { c.classList.add("done"); b.remove(); c.querySelector("small").textContent += " · passé ou annulé"; } });
  } else c.classList.add("done");
  return c;
}
function memoryCard(list) {
  const c = document.createElement("div");
  c.className = "acard";
  const txt = list.map((m) => m.content.replace(/^L'utilisateur\s+/i, "")).join(" · ");
  c.innerHTML = `<span class="ic">${icon("memory")}</span><div class="tx"><b>Retenu</b><small>${esc(txt)}</small></div>`;
  const b = document.createElement("button"); b.className = "btn sm"; b.textContent = "Oublier";
  b.onclick = async () => { for (const m of list) { try { await send_(`/api/memories/${m.id}`, "DELETE"); } catch {} } c.classList.add("done"); b.remove(); c.querySelector("b").textContent = "Oublié"; refreshPanel(); };
  c.appendChild(b);
  return c;
}

/* 4. Base de la réponse : sources web, bibliothèque, ou rien (à vérifier si ça ressemble à un fait précis) */
function basisEl(m) {
  const s = document.createElement("span");
  const nW = m.meta?.sources?.length || 0, nD = m.meta?.docs?.length || 0;
  if (nW || nD) {
    s.className = "basis";
    const parts = [];
    if (nD) parts.push(`${nD} passage${nD > 1 ? "s" : ""} de ta bibliothèque`);
    if (nW) parts.push(`${nW} source${nW > 1 ? "s" : ""} web`);
    s.innerHTML = icon("check") + "Basé sur " + esc(parts.join(" et "));
    return s;
  }
  const factual = /\b(1[6-9]|20)\d{2}\b|\d+[,.]?\d*\s?(€|\$|%|km|kg|go|to|mo|°)|\b\d{3,}\b/i.test(m.content || "");
  if (factual && (m.content || "").length > 60) {
    s.className = "basis warn"; s.title = "Atom a répondu de mémoire, sans document ni recherche : vérifie les chiffres et les dates.";
    s.innerHTML = "Sans source · à vérifier";
    return s;
  }
  return null;
}

/* « 2 souvenirs utilisés » : ce qu'Atom a pris en compte pour répondre */
function usedEl(used) {
  const facts = used.facts || [], recall = used.recall || [];
  const d = document.createElement("details");
  d.className = "used";
  const parts = [];
  if (facts.length) parts.push(`${facts.length} souvenir${facts.length > 1 ? "s" : ""}`);
  if (recall.length) parts.push(`${recall.length} ancienne${recall.length > 1 ? "s" : ""} conversation${recall.length > 1 ? "s" : ""}`);
  d.innerHTML = `<summary>${icon("memory")}${parts.join(" · ")} utilisé${facts.length + recall.length > 1 ? "s" : ""}</summary><ul></ul>`;
  const ul = d.querySelector("ul");
  for (const f of facts) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${esc(f.content)}</span>`;
    const b = document.createElement("button");
    b.textContent = "Oublier"; b.title = "Supprimer ce souvenir";
    b.onclick = async () => {
      try { await send_(`/api/memories/${f.id}`, "DELETE"); li.style.opacity = ".4"; li.querySelector("span").style.textDecoration = "line-through"; b.remove(); refreshPanel(); }
      catch { toast("Souvenir déjà supprimé."); }
    };
    li.appendChild(b);
    ul.appendChild(li);
  }
  for (const r of recall) {
    const li = document.createElement("li");
    li.innerHTML = `<span><small>Conversation passée · </small>${esc(r.text.slice(0, 160))}${r.text.length > 160 ? "…" : ""}</span>`;
    if (r.conversation_id) {
      const b = document.createElement("button");
      b.textContent = "Ouvrir";
      b.onclick = () => openConversation(r.conversation_id);
      li.appendChild(b);
    }
    ul.appendChild(li);
  }
  return d;
}

function actions(m, idx) {
  const a = document.createElement("div");
  a.className = "acts";
  const btn = (name, title, fn) => {
    const b = document.createElement("button");
    b.className = "iconbtn"; b.title = title; b.innerHTML = icon(name);
    b.onclick = fn; a.appendChild(b); return b;
  };
  if (m.role === "user") {
    if (m.created_at) { const t = document.createElement("time"); t.textContent = fmtTime(m.created_at); a.appendChild(t); }
    btn("copy", "Copier", (e) => flashCopy(e.currentTarget, m.content));
    if (m.id) btn("edit", "Modifier", () => editMessage(idx));
  } else {
    btn("copy", "Copier", (e) => flashCopy(e.currentTarget, m.content));
    btn("doc", "Ouvrir dans le canevas (modifier avec Atom)", () => canvasFromMessage(m));
    if (idx === history.length - 1) btn("refresh", "Régénérer", () => regenerate());
    if (idx === history.length - 1 && !m.meta?.provider && hybridState?.configured) btn("spark", `Réponse approfondie (${hybridState.name})`, () => regenerate("mistral"));
    if (m.id) {
      const up = btn("up2", "Bonne réponse", () => vote(m, 1, up, dn, a));
      const dn = btn("down2", "Mauvaise réponse", () => vote(m, -1, up, dn, a));
      up.classList.toggle("voted", m.feedback === 1); dn.classList.toggle("voted", m.feedback === -1);
    }
    if (m.created_at) { const t = document.createElement("time"); t.textContent = fmtTime(m.created_at); a.appendChild(t); }
    const bs = basisEl(m); if (bs) a.appendChild(bs);
    if (m.meta?.provider) { const v = document.createElement("span"); v.className = "via"; v.textContent = "via " + m.meta.provider; v.title = m.meta.remote_model || ""; a.appendChild(v); }
  }
  return a;
}

async function vote(m, value, up, dn, bar) {
  const v = m.feedback === value ? null : value;
  try { await send_(`/api/messages/${m.id}`, "PATCH", { value: v }); } catch { return; }
  m.feedback = v;
  up.classList.toggle("voted", v === 1); dn.classList.toggle("voted", v === -1);
  bar.parentElement.querySelector(".reason")?.remove();
  if (v === -1) {
    const r = document.createElement("div");
    r.className = "reason";
    r.innerHTML = '<input class="field" placeholder="Qu\'est-ce qui n\'allait pas ? (facultatif)"><button class="btn">Envoyer</button>';
    const inp = r.querySelector("input");
    const go = async () => { if (inp.value.trim()) await send_(`/api/messages/${m.id}`, "PATCH", { value: -1, reason: inp.value.trim() }); r.remove(); toast("Merci, c'est noté."); };
    r.querySelector("button").onclick = go;
    inp.onkeydown = (e) => { if (e.key === "Enter") go(); if (e.key === "Escape") r.remove(); };
    bar.after(r); inp.focus();
  } else if (v === 1) toast("Merci !");
}

function flashCopy(btn, text) {
  copyText(text);
  btn.innerHTML = icon("check");
  setTimeout(() => { btn.innerHTML = icon("copy"); }, 1300);
}

function renderHistory() {
  chat.innerHTML = "";
  if (!history.length) { renderEmpty(); return; }
  exitHero();
  history.forEach((m, i) => chat.appendChild(msgEl(m, i)));
  markLast();
  scroller.scrollTop = scroller.scrollHeight;
}
function markLast() {
  chat.querySelectorAll(".msg.last").forEach((x) => x.classList.remove("last"));
  const lastAtom = [...chat.querySelectorAll(".msg.atom")].pop();
  if (lastAtom && lastAtom === chat.lastElementChild) lastAtom.classList.add("last");
}

chat.addEventListener("click", (e) => {
  const b = e.target.closest("[data-copy]");
  if (!b) return;
  copyText(b.closest(".code").querySelector("pre").innerText);
  const old = b.innerHTML;
  b.innerHTML = icon("check") + "Copié";
  setTimeout(() => { b.innerHTML = old; }, 1300);
});

function editMessage(idx) {
  if (busy) return;
  const m = history[idx];
  const el = chat.querySelector(`.msg[data-idx="${idx}"]`);
  const box = document.createElement("div");
  box.className = "edit-box";
  box.innerHTML = `<textarea></textarea><div class="row"><button class="btn" data-a="cancel">Annuler</button><button class="btn primary" data-a="send">Envoyer</button></div>`;
  const ta = box.querySelector("textarea");
  ta.value = m.content;
  el.innerHTML = ""; el.appendChild(box);
  ta.style.height = ta.scrollHeight + "px"; ta.focus();
  box.querySelector('[data-a="cancel"]').onclick = () => renderHistory();
  box.querySelector('[data-a="send"]').onclick = async () => {
    const v = ta.value.trim();
    if (!v) return;
    await send_(`/api/conversations/${settings.conversationId}/truncate`, "POST", { from_id: m.id });
    history = history.slice(0, idx);
    renderHistory();
    sendMessage(v);
  };
  ta.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); box.querySelector('[data-a="send"]').click(); } if (e.key === "Escape") renderHistory(); };
}

async function regenerate(withEngine) {
  if (busy) return;
  let i = history.length - 1;
  while (i >= 0 && history[i].role !== "user") i--;
  if (i < 0 || !history[i].id) return;
  const text = history[i].content;
  await send_(`/api/conversations/${settings.conversationId}/truncate`, "POST", { from_id: history[i].id });
  history = history.slice(0, i);
  renderHistory();
  if (withEngine) engineOverride = withEngine;
  sendMessage(text);
}

/* scroll */
function atBottom() { return scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 60; }
scroller.addEventListener("scroll", () => {
  $("toBottom").classList.toggle("on", !atBottom());
  $("topbar").classList.toggle("scrolled", scroller.scrollTop > 4);
});
$("toBottom").onclick = () => scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });

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
    else sendMessage(text, files);
  }
});

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
        } else if (ev.type === "reminder") {
          if (ev.action === "created" || ev.action === "cancelled") { remCards.push(ev); pendingReminders = null; }
          if (ev.action === "created") toast(`<b>Rappel programmé</b> · ${esc(ev.when)} — ${esc(ev.text)}`);
          else if (ev.action === "cancelled") toast(`<b>Rappel annulé</b>`);
          else toast(`<b>Rappel non programmé</b> · ${esc(ev.message)}`);
          refreshPanel();
        } else if (ev.type === "done") {
          emotion = ev.emotion; asstId = ev.id;
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

/* ============================================================
   PANNEAU : système, rappels, souvenirs
   ============================================================ */
async function refreshSystem() {
  if (!panelVisible()) return;
  try {
    const s = await getJSON("/api/system");
    if (s.cpu != null) entity.load = Math.max(0, Math.min(1, (s.cpu - 10) / 80));
    if (s.cpu != null) { $("cpuV").textContent = `${Math.round(s.cpu)} %${s.cores ? ` · ${s.cores} cœurs` : ""}`; $("cpuB").style.width = Math.min(100, s.cpu) + "%"; }
    if (s.memory) { $("ramV").textContent = `${fmtBytes(s.memory.used)} / ${fmtBytes(s.memory.total)}`; $("ramB").style.width = (100 * s.memory.used / s.memory.total) + "%"; }
    $("loadedV").textContent = s.loaded.length ? s.loaded.map((m) => m.name.split(":")[0] + (m.size ? ` · ${fmtBytes(m.size)}` : "")).join(", ") : "aucun (en veille)";
    $("upV").textContent = fmtDur(s.uptime);
  } catch {}
}

// Ligne « aujourd'hui » de l'accueil : rappels du jour, état du serveur, mémoire
async function renderToday() {
  const box = $("today"); if (!box) return;
  const parts = [];
  try {
    const r = (await getJSON("/api/reminders")).reminders;
    const end = new Date(); end.setHours(23, 59, 59, 999);
    const today = r.filter((x) => x.due_at * 1000 <= end.getTime());
    parts.push(`<button data-go="reminders"><span class="dot${today.length ? " warn" : ""}"></span>${today.length ? `${today.length} rappel${today.length > 1 ? "s" : ""} aujourd'hui` : "aucun rappel aujourd'hui"}</button>`);
  } catch {}
  try {
    const p = await getJSON("/api/proxmox");
    if (p.configured) {
      const n = p.alerts?.length || 0, run = p.guests.filter((g) => g.status === "running").length;
      parts.push(`<button data-go="proxmox"><span class="dot ${!p.ok ? "err" : n ? "warn" : "ok"}"></span>${!p.ok ? "serveur injoignable" : n ? `${n} alerte${n > 1 ? "s" : ""} serveur` : `serveur OK · ${run} en marche`}</button>`);
    }
  } catch {}
  try {
    const m = (await getJSON("/api/memories")).memories.length;
    if (m) parts.push(`<button data-go="memory"><span class="dot"></span>${m} souvenir${m > 1 ? "s" : ""}</button>`);
  } catch {}
  if (!$("today")) return;
  box.innerHTML = parts.join("");
  box.querySelectorAll("[data-go]").forEach((b) => { b.onclick = () => openSettings(b.dataset.go); });
}
async function refreshPanel() {
  if (!panelVisible()) return;
  try {   // serveur Proxmox (si configuré)
    const p = await getJSON("/api/proxmox");
    $("pxSec").hidden = !p.configured;
    if (p.configured) {
      const n = p.nodes[0], run = p.guests.filter((g) => g.status === "running").length;
      $("pxMini").innerHTML = !p.ok ? `<p class="alert">Injoignable : ${esc(p.error)}</p>` : `<div class="px-mini">
        ${(p.alerts || []).map((a) => `<p class="alert">⚠ ${esc(a.title)}</p>`).join("")}
        ${n ? `<div class="metric"><div class="l"><span>${esc(n.name)} · processeur</span><span>${n.cpu.toFixed(0)} %</span></div><div class="bar"><i style="width:${n.cpu}%"></i></div></div>
        <div class="metric"><div class="l"><span>Mémoire</span><span>${n.mem.toFixed(0)} %</span></div><div class="bar"><i style="width:${n.mem}%"></i></div></div>` : ""}
        <div class="kv"><span>Invités en marche</span><span>${run} / ${p.guests.length}</span></div></div>`;
      $("pxMini").onclick = () => openSettings("proxmox");
    }
  } catch { $("pxSec").hidden = true; }
  try {
    const r = (await getJSON("/api/reminders")).reminders.slice(0, 3);
    $("pRem").innerHTML = r.length
      ? r.map((x) => `<li><small>${esc(x.when)}</small>${esc(x.text)}</li>`).join("")
      : '<li class="none">Aucun rappel programmé.</li>';
  } catch {}
  try {
    const m = (await getJSON("/api/memories")).memories.slice(-4).reverse();
    $("pMem").innerHTML = m.length
      ? m.map((x) => `<li>${esc(x.content)}</li>`).join("")
      : '<li class="none">Rien de retenu pour l\'instant.</li>';
  } catch {}
}
document.querySelectorAll("[data-goto]").forEach((b) => { b.onclick = () => openSettings(b.dataset.goto); });

/* ============================================================
   RÉGLAGES
   ============================================================ */
// Cinq groupes ; chaque ancien panneau devient une section de son groupe.
const SET_GROUPS = {
  atom: ["general", "look", "entity"],
  discussion: ["workshop"],
  data: ["memory", "reminders", "backup"],
  connections: ["hybrid"],
  system: ["status", "proxmox", "lab", "security"],
};
const PANE_TITLES = { general: "Général", look: "Apparence", entity: "Entité", workshop: "Atelier multi-IA", memory: "Souvenirs",
  reminders: "Rappels", backup: "Sauvegarde", hybrid: "Mode hybride", status: "État", proxmox: "Serveur Proxmox", lab: "Modèles locaux", security: "Sécurité" };
const PANE_LOAD = { memory: () => loadMemories(), reminders: () => loadReminders(), backup: () => loadBackups(), status: () => loadStatus(),
  security: () => loadSecurity(), hybrid: () => loadHybrid(), workshop: () => loadWorkshop(), lab: () => loadLab(), proxmox: () => loadProxmox() };
const setGroupOf = (pane) => Object.keys(SET_GROUPS).find((g) => SET_GROUPS[g].includes(pane)) || pane;
document.querySelectorAll(".pane").forEach((p) => {
  const h = document.createElement("h3"); h.className = "pane-title"; h.textContent = PANE_TITLES[p.dataset.pane] || ""; p.prepend(h);
});
function openSettings(tab = "atom") {
  $("settings").classList.add("open");
  selectTab(tab);
}
function closeSettings() { $("settings").classList.remove("open"); }
function selectTab(tab) {
  const g = setGroupOf(tab), panes = SET_GROUPS[g] || [];
  $("setSearch").value = ""; filterSettings("");
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.tab === g));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", panes.includes(p.dataset.pane)));
  panes.forEach((p) => PANE_LOAD[p] && PANE_LOAD[p]());
  const target = document.querySelector(`.pane[data-pane="${tab}"]`);
  if (target && tab !== panes[0]) requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
  else document.querySelector(".pane-wrap").scrollTop = 0;
}
// Recherche : affiche, tous groupes confondus, les blocs dont le texte correspond.
const norm = (x) => x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
function filterSettings(q) {
  q = norm(q.trim());
  $("settings").classList.toggle("searching", !!q);
  if (!q) { document.querySelectorAll(".pane .block").forEach((b) => (b.hidden = false)); return; }
  let any = false;
  document.querySelectorAll(".pane").forEach((p) => {
    let hit = false;
    p.querySelectorAll(".block").forEach((b) => { const m = norm(b.textContent).includes(q); b.hidden = !m; hit = hit || m; });
    p.classList.toggle("on", hit); any = any || hit;
    if (hit && PANE_LOAD[p.dataset.pane]) PANE_LOAD[p.dataset.pane]();
  });
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("on"));
  $("setEmpty").hidden = any;
}
$("setSearch").oninput = () => filterSettings($("setSearch").value);
document.querySelectorAll(".tab").forEach((t) => { t.onclick = () => selectTab(t.dataset.tab); });
$("openSettings").onclick = () => openSettings();
$("closeSettings").onclick = closeSettings;
$("settings").addEventListener("click", (e) => { if (e.target.id === "settings") closeSettings(); });

$("persona").value = settings.persona;
$("persona").oninput = () => { settings.persona = $("persona").value; saveSettings(); };
$("autoMem").checked = settings.autoMemory;
$("autoMem").onchange = () => { settings.autoMemory = $("autoMem").checked; saveSettings(); };
$("reconnect").onclick = () => connect(true);

let memories = [];
async function loadMemories() {
  try { memories = (await getJSON("/api/memories")).memories; } catch (e) { console.warn(e); }
  const box = $("memList");
  box.innerHTML = "";
  for (const m of memories) {
    const row = document.createElement("div");
    row.className = "mem";
    const tag = document.createElement("span");
    tag.className = "tag"; tag.textContent = m.source === "auto" ? "auto" : "manuel";
    tag.title = m.source === "auto" ? "Retenu automatiquement" : "Ajouté par toi";
    const inp = document.createElement("input");
    inp.value = m.content;
    const del = document.createElement("button");
    del.className = "iconbtn"; del.title = "Oublier"; del.innerHTML = icon("trash");
    del.onclick = async () => { try { await send_(`/api/memories/${m.id}`, "DELETE"); } catch {} loadMemories(); refreshPanel(); };
    inp.onchange = async () => {
      const v = inp.value.trim();
      if (!v) return del.onclick();
      try { await send_(`/api/memories/${m.id}`, "PATCH", { content: v }); m.content = v; refreshPanel(); }
      catch (e) { toast(esc(e.message)); inp.value = m.content; }
    };
    row.append(tag, inp, del);
    box.appendChild(row);
  }
  $("memInfo").textContent = memories.length
    ? `${memories.length} souvenir(s). Atom retient seul les informations durables ; modifie ou supprime ce qui ne te convient pas.`
    : "Atom n'a encore rien retenu. Il apprendra au fil des conversations.";
}
$("memAdd").onclick = async () => {
  const v = $("memNew").value.trim();
  if (!v) return;
  try { await send_("/api/memories", "POST", { content: v }); $("memNew").value = ""; } catch (e) { toast(esc(e.message)); }
  loadMemories(); refreshPanel();
};
$("memNew").onkeydown = (e) => { if (e.key === "Enter") $("memAdd").onclick(); };
$("clearMem").onclick = async () => {
  if (!confirm("Effacer tout ce qu'Atom sait de toi ?")) return;
  try { await send_("/api/memories", "DELETE"); } catch {}
  loadMemories(); refreshPanel();
};

async function loadReminders() {
  let data = { reminders: [], notifications: false };
  try { data = await getJSON("/api/reminders"); } catch {}
  const ul = $("remList");
  ul.innerHTML = data.reminders.length ? "" : '<li class="none">Aucun rappel programmé.</li>';
  for (const r of data.reminders) {
    const li = document.createElement("li");
    li.style.display = "flex"; li.style.alignItems = "center"; li.style.gap = "10px";
    li.innerHTML = `<div style="flex:1"><small>${esc(r.when)}</small>${esc(r.text)}</div>`;
    const del = document.createElement("button");
    del.className = "iconbtn"; del.title = "Annuler"; del.innerHTML = icon("trash");
    del.onclick = async () => { try { await send_(`/api/reminders/${r.id}`, "DELETE"); } catch {} loadReminders(); refreshPanel(); };
    li.appendChild(del);
    ul.appendChild(li);
  }
  $("remInfo").textContent = data.notifications ? "" : "Aucun canal de notification configuré (ntfy ou Telegram) : les rappels n'apparaîtront que dans la conversation.";
}
$("notifTest").onclick = async () => {
  try { await send_("/api/notify/test", "POST"); toast("<b>Notification envoyée</b> · regarde ton téléphone."); }
  catch (e) { toast(esc(e.message)); }
};

for (const e of EMOTIONS) {
  const b = document.createElement("button");
  b.className = "chip"; b.textContent = ACTIVITIES[e].label;
  b.onclick = () => setEmotion(e);
  $("emos").appendChild(b);
}
const DEMOS = [
  ["Travail long · recherche web", () => { entity.feedColor = [110, 170, 255]; entity.feeding = true; setTimeout(() => { entity.feeding = false; }, 4000); }],
  ["Travail long · documents", () => { entity.scan = true; setTimeout(() => { entity.scan = false; }, 4000); }],
  ["Travail long · IA distante", () => { entity.remote = true; setTimeout(() => { entity.remote = false; }, 4000); }],
  ["Travail long · atelier / agent", () => { entity.split = 2; setTimeout(() => { entity.split = 0; }, 4000); }],
];
const demoRow = document.createElement("div");
demoRow.className = "emos"; demoRow.style.marginTop = "12px";
for (const [label, fn] of DEMOS) { const b = document.createElement("button"); b.className = "chip"; b.textContent = label; b.onclick = fn; demoRow.appendChild(b); }
$("emos").after(demoRow);

/* ============================================================
   CONNEXION
   ============================================================ */
const modelSel = $("model");
let online = false;
async function connect(verbose = false) {
  let info = "", ok = false, err = false;
  try {
    const h = await getJSON("/api/health");
    ok = h.ollama && h.model_ready;
    info = h.provider === "mock" ? "Mode test"
      : !h.ollama ? "Ollama injoignable"
      : !h.model_ready ? "Aucun modèle installé"
      : "En ligne";
    err = !h.ollama;
    const details = [
      h.provider === "mock" ? "Mode test, sans modèle." : h.ollama ? "Ollama joignable." : "Ollama injoignable depuis le serveur.",
      h.embeddings ? "Mémoire sémantique active." : "Mémoire sans recherche sémantique (nomic-embed-text absent).",
      h.telegram ? "Telegram activé." : "Telegram désactivé.",
      h.search ? "Recherche web disponible." : "Recherche web désactivée.",
    ];
    searchAvailable = !!h.search; renderWebBtn(); if (searchAvailable && !document.querySelector("#empty .card[data-cap]")) renderCards();
    $("webInfo").textContent = h.search ? "" : "Le service de recherche (SearXNG) n'est pas configuré sur le serveur.";
    $("srvInfo").textContent = details.join(" ");
    if (h.ollama) {
      const m = await getJSON("/api/models");
      const prev = modelSel.value;
      modelSel.innerHTML = "";
      if (!m.models.length) modelSel.add(new Option("Aucun modèle", ""));
      for (const n of m.models) modelSel.add(new Option(n, n));
      if (!m.models.includes(settings.model)) { settings.model = m.models.includes(m.default) ? m.default : (m.models[0] || ""); saveSettings(); }
      const c = currentConv();
      modelSel.value = (c?.model && m.models.includes(c.model)) ? c.model : (settings.model || prev);
    }
  } catch {
    info = "Serveur injoignable"; err = true;
    $("srvInfo").textContent = "Le serveur Atom ne répond pas.";
  }
  if (!modelSel.options.length) modelSel.add(new Option(settings.model || "Hors ligne", settings.model));
  online = ok;
  $("dot").className = "dot" + (ok ? " on" : err ? " err" : "");
  $("statusText").textContent = info;
  if (verbose) toast(esc($("srvInfo").textContent));
}
modelSel.onchange = () => {
  settings.model = modelSel.value; saveSettings();
  const c = currentConv();
  toast(c ? `Modèle de cette conversation : <b>${esc(modelSel.value)}</b>` : `Modèle : <b>${esc(modelSel.value)}</b>`);
};

/* ============================================================
   FICHIERS JOINTS (glisser-déposer, coller, bouton trombone)
   ============================================================ */
let pending = [];   // [{name, text, pages, loading}]
function renderTray() {
  const tray = $("tray");
  tray.innerHTML = "";
  pending.forEach((f, i) => tray.appendChild(fileChip(f, () => { pending.splice(i, 1); renderTray(); })));
  autoGrow();
}
function toBase64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",")[1] || "");
    r.onerror = rej;
    r.readAsDataURL(file);
  });
}
async function addFiles(list) {
  for (const file of list) {
    if (pending.length >= 5) { toast("5 fichiers maximum par message."); break; }
    if (file.size > 15 * 1024 * 1024) { toast(`<b>${esc(file.name)}</b> · trop gros (15 Mo max).`); continue; }
    if (/\.(csv|tsv|xlsx|xls|json|parquet)$/i.test(file.name) && sbGlobal?.enabled) {
      // fichier de données : analysé par Python dans le bac à sable (le fichier ne quitte pas le serveur)
      const item = { name: file.name, text: "", loading: true, data: true, chars: file.size };
      pending.push(item); renderTray();
      try { item.b64 = await toBase64(file); item.loading = false; } catch { pending.splice(pending.indexOf(item), 1); }
      renderTray();
      if (pending.filter((f) => f.data).length === 1) toast(`<b>${esc(file.name)}</b> · pose ta question : Atom l'analysera avec Python (graphiques compris).`);
      continue;
    }
    const item = { name: file.name, text: "", loading: true };
    pending.push(item); renderTray();
    try {
      const r = await (await api("/api/extract", { method: "POST", body: JSON.stringify({ name: file.name, data: await toBase64(file) }) })).json();
      Object.assign(item, { text: r.text, pages: r.pages, loading: false });
      if (r.text.length > 12000) toast(`<b>${esc(file.name)}</b> · long fichier : seuls les 12 000 premiers caractères seront lus.`);
    } catch (e) {
      pending.splice(pending.indexOf(item), 1);
      toast(`<b>${esc(file.name)}</b> · ${esc(e.message)}`);
    }
    renderTray();
  }
  input.focus();
}
$("attach").onclick = () => $("fileIn").click();
$("fileIn").onchange = (e) => { addFiles([...e.target.files]); e.target.value = ""; };
let dragDepth = 0;
addEventListener("dragenter", (e) => { if ([...(e.dataTransfer?.types || [])].includes("Files")) { dragDepth++; $("drop").classList.add("on"); } });
addEventListener("dragleave", () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $("drop").classList.remove("on"); });
addEventListener("dragover", (e) => e.preventDefault());
addEventListener("drop", (e) => {
  e.preventDefault(); dragDepth = 0; $("drop").classList.remove("on");
  if (!e.dataTransfer?.files?.length) return;
  if (!$("libView").hidden) {
    const c = library.collections.find((x) => x.id === libSel && x.kind === "docs") || library.collections.find((x) => x.kind === "docs");
    if (c) uploadDocs(c.id, [...e.dataTransfer.files]);
    return;
  }
  addFiles([...e.dataTransfer.files]);
});
input.addEventListener("paste", (e) => {
  const files = [...(e.clipboardData?.files || [])];
  if (files.length) { e.preventDefault(); addFiles(files); }
});

/* ============================================================
   BROUILLONS (un par conversation)
   ============================================================ */
const draftKey = () => "draft." + (settings.conversationId || "new");
let draftTimer = 0;
function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    try { input.value ? localStorage.setItem("atom." + draftKey(), input.value) : localStorage.removeItem("atom." + draftKey()); } catch {}
  }, 250);
}
function clearDraft() { clearTimeout(draftTimer); try { localStorage.removeItem("atom." + draftKey()); } catch {} }
function restoreDraft() {
  let v = "";
  try { v = localStorage.getItem("atom." + draftKey()) || ""; } catch {}
  input.value = v; autoGrow();
}

/* ============================================================
   APPARENCE (densité, largeur)
   ============================================================ */
function applyLook() {
  document.body.classList.toggle("compact", settings.density === "compact");
  document.body.classList.toggle("wide", settings.width === "wide");
  document.body.classList.toggle("narrow", settings.width === "narrow");
}
function choiceRow(id, key, options) {
  const row = $(id);
  row.innerHTML = "";
  for (const [val, label] of options) {
    const b = document.createElement("button");
    b.className = "btn" + ((settings[key] || options[0][0]) === val ? " primary" : "");
    b.textContent = label;
    b.onclick = () => { settings[key] = val; saveSettings(); applyLook(); choiceRow(id, key, options); };
    row.appendChild(b);
  }
}
choiceRow("densityRow", "density", [["comfort", "Confortable"], ["compact", "Compacte"]]);
choiceRow("styleRow", "entityStyle", [["mesh", "Maillage"], ["fragments", "Fragments"], ["orb", "Planète"]]);
choiceRow("widthRow", "width", [["normal", "Normale"], ["narrow", "Étroite"], ["wide", "Large"]]);

/* ============================================================
   HUMEUR (teinte de repos) et rythme jour / nuit
   ============================================================ */
async function refreshMood() {
  let data;
  try { data = await getJSON("/api/mood?hours=24"); } catch { return; }
  let w = 0, v = 0;
  for (const e of data.events) { const k = Math.pow(0.5, (data.now - e.created_at) / 10800); w += k; v += k * (VALENCE[e.emotion] ?? 0); }
  entity.mood = w ? v / w * Math.min(1, w) : 0;
}
function checkNight() {
  const h = new Date().getHours();
  entity.night = h >= 23 || h < 6;
}

/* ============================================================
   MODE PRÉSENCE — la sphère quitte son panneau et occupe l'écran.
   Le canvas passe en plein écran d'un coup (invisible : la sphère est
   dessinée au même endroit), puis c'est le dessin qui glisse et grandit,
   sur une seule courbe. Aucun redimensionnement pendant l'animation.
   ============================================================ */
const stageEl = $("stage");
let presenceOn = false, presenceBusy = false, placeholder = null, wakeLock = null, clockTimer = 0;

function tickClock() {
  const d = new Date();
  $("pClock").textContent = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  $("pDate").textContent = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  $("pEmoBig").textContent = ACTIVITIES[entity.activity].label.toLowerCase();
}
function presenceSay(text, label = "Atom") {
  if (!text) return;
  const plain = text.replace(/```[\s\S]*?```/g, "[code]").replace(/[#*_`>|]/g, "").replace(/\s+/g, " ").trim();
  $("pSay").innerHTML = `<small>${esc(label)}</small>${esc(plain.length > 220 ? plain.slice(0, 217) + "…" : plain)}`;
}

entity.panelRect = () => {
  if (placeholder && placeholder.isConnected) {
    const r = placeholder.getBoundingClientRect();
    if (r.width > 10) return r;
  }
  const b = $("presenceBtn").getBoundingClientRect();   // panneau fermé : la sphère naît du bouton
  return { left: b.left, top: b.top, width: b.width, height: b.height };
};

function flyTo(to, dur, onEnd) {
  const f = entity.fly;
  Object.assign(f, { from: f.p, to, start: performance.now(), dur, active: true, onEnd });
}

let heroOn = false, heroBusy = false;
function stageOut(cls) {
  placeholder = document.createElement("div");
  placeholder.className = "stage-ph" + (cls ? " " + cls : "");
  placeholder.style.height = stageEl.offsetHeight + "px";
  stageEl.after(placeholder);
  document.body.appendChild(stageEl);
  stageEl.classList.add("flying");
  entity.flying = true;
}
function stageBack() {
  stageEl.classList.remove("flying");
  entity.flying = false;
  placeholder?.replaceWith(stageEl);
  placeholder = null;
}
entity.heroRect = () => $("heroSlot")?.getBoundingClientRect() || null;
function enterHero() {
  if (settings.heroWelcome === false || heroOn || heroBusy || presenceOn || presenceBusy || currentView !== "chat") return;
  if (!$("heroSlot") || narrow()) return;
  heroBusy = true; heroOn = true;
  entity.target = "hero";
  stageOut("hero-ph");
  document.body.classList.add("hero");
  requestAnimationFrame(() => { if (placeholder) placeholder.style.height = "0px"; });   // le panneau remonte ses rubriques
  flyTo(1, 1000, () => { heroBusy = false; });
}
function exitHero(cb) {
  if (!heroOn) { cb && cb(); return; }
  heroBusy = true;
  document.body.classList.remove("hero");
  if (placeholder) placeholder.style.height = "360px";   // la place revient pendant le retour de l'entité
  flyTo(0, 750, () => { stageBack(); heroOn = false; heroBusy = false; entity.target = "full"; cb && cb(); });
}

async function enterPresence() {
  if (heroOn) { exitHero(() => enterPresence()); return; }
  if (presenceOn || presenceBusy) return;
  entity.target = "full";
  presenceBusy = true;
  stageOut("");
  document.body.classList.add("presence");
  flyTo(1, 1100, () => {
    presenceOn = true; presenceBusy = false;
    document.body.classList.add("presence-ui");
  });
  entity.rippleT = 0;
  tickClock(); clockTimer = setInterval(tickClock, 10000);
  try { wakeLock = await navigator.wakeLock?.request("screen"); } catch {}
  try { await document.documentElement.requestFullscreen?.({ navigationUI: "hide" }); } catch {}
}

function exitPresence() {
  if (!presenceOn || presenceBusy) return;
  presenceBusy = true;
  document.body.classList.remove("presence-ui");
  clearInterval(clockTimer);
  try { wakeLock?.release(); } catch {}
  wakeLock = null;
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  setTimeout(() => {
    document.body.classList.remove("presence");
    entity.rippleT = 0;
    flyTo(0, 1000, () => {
      // La sphère est exactement au-dessus de sa place : on la range.
      stageBack();
      presenceOn = false; presenceBusy = false;
    });
  }, 220);
}
stageEl.addEventListener("click", (e) => {
  if (e.target.closest("button") || entity.wasLongPress()) return;
  if (presenceBusy) return;
  presenceOn ? exitPresence() : enterPresence();
});
$("presenceBtn").onclick = enterPresence;
document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement && presenceOn) exitPresence(); });

/* ============================================================
   APPLICATION INSTALLABLE (PWA)
   ============================================================ */
let installEvt = null;
if ("serviceWorker" in navigator && isSecureContext) navigator.serviceWorker.register("/sw.js").catch(() => {});
addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installEvt = e; $("installBtn").style.display = ""; });
$("installBtn").onclick = async () => { if (!installEvt) return; installEvt.prompt(); await installEvt.userChoice; installEvt = null; $("installBtn").style.display = "none"; };
(function installHint() {
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  $("installInfo").textContent = standalone ? "Atom est installé sur cet appareil."
    : !isSecureContext ? "L'installation demande une connexion HTTPS. Avec Tailscale (voir le README), ouvre Atom via son adresse https://…ts.net : le bouton d'installation apparaîtra ici."
    : /iphone|ipad/i.test(navigator.userAgent) ? "Sur iPhone : bouton Partager → « Sur l'écran d'accueil »."
    : "Utilise le bouton ci-dessous, ou le menu du navigateur → « Installer l'application ».";
})();

/* ============================================================
   RECHERCHE WEB (bouton globe + réglage)
   ============================================================ */
let webForce = false, searchAvailable = true;
function renderWebBtn() {
  const b = $("webBtn");
  b.classList.toggle("on", webForce);
  b.style.display = searchAvailable ? "" : "none";
  b.title = webForce ? "Recherche Internet activée pour ce message (clic pour annuler)"
    : settings.webAuto === false ? "Rechercher sur Internet pour ce message" : "Forcer une recherche Internet (sinon Atom décide)";
}
$("webBtn").onclick = () => { webForce = !webForce; renderWebBtn(); input.focus(); };
$("webAuto").checked = settings.webAuto !== false;
$("webAuto").onchange = () => { settings.webAuto = $("webAuto").checked; saveSettings(); renderWebBtn(); };

document.querySelectorAll(".side-nav [data-goto]").forEach((b) => { b.onclick = () => openSettings(b.dataset.goto); });
async function refreshCounts() {
  try { const m = (await getJSON("/api/memories")).memories.length; $("navMem").textContent = m || ""; } catch {}
  try { const r = (await getJSON("/api/reminders")).reminders.length; $("navRem").textContent = r || ""; } catch {}
}

/* ============================================================
   SAUVEGARDE ET VITESSE
   ============================================================ */
async function loadBackups() {
  let d;
  try { d = await getJSON("/api/backups"); } catch { return; }
  $("bkInfo").textContent = `Atom copie toute sa mémoire (conversations, souvenirs, rappels) chaque nuit à ${d.time}, et garde les ${d.keep} dernières copies dans le dossier « backups » du serveur.`;
  const label = { auto: "automatique", manual: "manuelle", export: "téléchargée", prerestore: "avant restauration", "": "" };
  $("bkList").innerHTML = d.backups.length ? "" : '<li class="none">Aucune sauvegarde pour l\'instant.</li>';
  for (const b of d.backups) {
    const li = document.createElement("li");
    li.style.cssText = "display:flex;align-items:center;gap:8px";
    li.innerHTML = `<div style="flex:1"><small>${esc(new Date(b.created_at * 1000).toLocaleString("fr-FR"))} · ${fmtBytes(b.size)}</small>${esc(label[b.tag] ?? b.tag)}</div>`;
    const dl = document.createElement("a");
    dl.className = "iconbtn"; dl.title = "Télécharger"; dl.href = `/api/backups/${encodeURIComponent(b.name)}/download`; dl.innerHTML = icon("download");
    const rs = document.createElement("button");
    rs.className = "btn"; rs.textContent = "Restaurer";
    rs.onclick = async () => {
      if (!confirm("Restaurer cette sauvegarde ? L'état actuel sera sauvegardé avant.")) return;
      try { await send_(`/api/backups/${encodeURIComponent(b.name)}/restore`, "POST"); toast("<b>Mémoire restaurée</b> · rechargement…"); setTimeout(() => location.reload(), 900); }
      catch (e) { toast(esc(e.message)); }
    };
    li.append(dl, rs);
    $("bkList").appendChild(li);
  }
}
$("bkNow").onclick = async () => { try { await send_("/api/backups", "POST"); entity.seal = 1; toast("<b>Sauvegarde créée</b>"); } catch (e) { toast(esc(e.message)); } loadBackups(); };
$("bkExport").onclick = () => { location.href = "/api/export"; setTimeout(loadBackups, 1500); };
$("bkImport").onclick = () => $("bkFile").click();
$("bkFile").onchange = async (e) => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f || !confirm(`Restaurer « ${f.name} » ? L'état actuel sera sauvegardé avant.`)) return;
  try {
    const r = await fetch("/api/import", { method: "POST", body: f, headers: { "Content-Type": "application/octet-stream", "X-Atom": "1" } });
    if (!r.ok) throw new Error((await r.json()).detail || "Échec");
    toast("<b>Mémoire restaurée</b> · rechargement…"); setTimeout(() => location.reload(), 900);
  } catch (err) { toast(esc(err.message)); }
};
$("benchBtn").onclick = async () => {
  $("benchInfo").textContent = "Mesure en cours (le modèle écrit une phrase)…";
  try {
    const r = await (await api("/api/benchmark", { method: "POST" })).json();
    const tips = r.tok_s == null ? "" : r.tok_s < 3 ? " · Lent : voir « Vitesse » dans le README." : r.tok_s < 7 ? " · Correct pour un CPU." : " · Bonne vitesse.";
    $("benchInfo").textContent = r.tok_s == null ? `Terminé en ${r.wall_s} s.`
      : `Écriture : ${r.tok_s} tok/s · lecture du contexte : ${r.prompt_tok_s ?? "—"} tok/s · chargement du modèle : ${r.load_s} s${tips}`;
    if (r.tok_s) $("speedV").textContent = r.tok_s.toFixed(1) + " tok/s";
  } catch (e) { $("benchInfo").textContent = e.message; }
};

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

/* ============================================================
   BIBLIOTHÈQUE — documents et projets de code
   ============================================================ */
let library = { collections: [], server_projects: [] }, libSel = null, libTimer = 0;
let scope = store.get("scope", "auto");   // "auto" | "none" | "3,5"

let currentView = "chat";
function showView(v) {
  currentView = v; store.set("view", v); app.dataset.view = v; applyLayout();
  $("libView").hidden = v !== "library";
  $("codeView").hidden = v !== "code";
  $("scroller").hidden = v !== "chat";
  document.querySelector(".composer").hidden = v !== "chat";
  $("navLib").classList.toggle("on", v === "library");
  $("navCode").classList.toggle("on", v === "code");
  ["pinBtn", "exportBtn"].forEach((id) => { if (v !== "chat") $(id).style.display = "none"; });
  app.classList.remove("side-open");
  if (v !== "chat") exitHero();
  else if (!history.length) requestAnimationFrame(() => enterHero());
  if (v === "library") { $("title").textContent = "Bibliothèque"; loadLibrary(); }
  else if (v === "code") { $("title").textContent = "Code"; loadCodeProjects(); }
  else { updateTitle(); if (!library.collections.some((c) => c.status === "indexing")) clearTimeout(libTimer); }
  if (typeof syncTabbar === "function") syncTabbar();
}
$("navLib").onclick = () => showView(currentView === "library" ? "chat" : "library");
$("navCode").onclick = () => showView(currentView === "code" ? "chat" : "code");

async function loadLibrary() {
  try { library = await getJSON("/api/library"); } catch { return; }
  if (!libSel || !library.collections.some((c) => c.id === libSel)) libSel = library.collections[0]?.id ?? null;
  const hadCols = !!library.collections.length;
  renderLibrary();
  renderScope();
  if (hadCols && !document.querySelector("#empty .card[data-cap]")) renderCards();
  const busyIdx = library.collections.some((c) => c.status === "indexing");
  entity.feedColor = busyIdx ? [235, 235, 240] : [110, 170, 255];
  if (!$("libView").hidden || !$("codeView").hidden) entity.feeding = busyIdx;
  watchIndexing();
  clearTimeout(libTimer);
  // Pendant une indexation, on suit la progression quelle que soit la vue (et on prévient à la fin).
  if (busyIdx || !$("libView").hidden) libTimer = setTimeout(loadLibrary, busyIdx ? 2000 : 15000);
}

// ---- suivi des indexations : progression lisible + notification de fin
const idxSeen = new Map();   // id → { status, phase, done, t }
function idxText(c) {
  const p = c.progress;
  if (c.status !== "indexing") return c.message || "";
  if (!p) return c.message || "Indexation…";
  if (p.phase === "clone") return "Téléchargement du dépôt…";
  if (p.phase === "read") return `Lecture de ${p.total} fichiers…`;
  if (p.phase === "embed") {
    if (!p.total) return "Finalisation…";
    const pct = Math.floor((100 * p.done) / p.total);
    const s = idxSeen.get(c.id), rate = s?.rate;
    const left = rate > 0 ? Math.max(1, Math.round((p.total - p.done) / rate)) : 0;
    return `Indexation : ${p.done} / ${p.total} passages · ${pct} %` + (left ? ` · ~${left < 90 ? left + " s" : Math.round(left / 60) + " min"}` : "");
  }
  return c.message || "Indexation…";
}
function idxPct(c) {
  const p = c.progress;
  if (c.status !== "indexing" || !p) return null;
  return p.phase === "embed" && p.total ? p.done / p.total : p.phase === "read" ? 0.02 : 0;
}
function watchIndexing() {
  const now = performance.now() / 1000;
  for (const c of library.collections) {
    const prev = idxSeen.get(c.id), p = c.progress || {};
    const cur = { status: c.status, phase: p.phase, done: p.done || 0, t: now, rate: prev?.rate || 0 };
    if (prev && prev.phase === "embed" && p.phase === "embed" && cur.done > prev.done) {
      const r = (cur.done - prev.done) / Math.max(0.5, now - prev.t);
      cur.rate = prev.rate ? prev.rate * 0.6 + r * 0.4 : r;
    }
    if (prev && prev.status === "indexing" && c.status !== "indexing") {
      if (c.status === "ready") toast(`<b>${esc(c.name)}</b> · prêt : ${c.documents} fichiers, ${c.chunks} passages indexés.`);
      else if (c.status === "error") toast(`<b>${esc(c.name)}</b> · ${esc(c.message || "indexation impossible")}`);
    }
    // le projet ouvert dans la vue Code : la liste des fichiers arrive dès la fin de la lecture
    if (!$("codeView").hidden && c.id === code.project && prev
        && (prev.status !== c.status || (prev.phase !== p.phase && p.phase === "embed"))) loadCodeFiles();
    else if (!$("codeView").hidden && c.id === code.project) renderCodeInfo(c);
    idxSeen.set(c.id, cur);
  }
}
// lancée depuis l'interface : la fin sera signalée même si elle survient avant le premier relevé
function markIndexing(id) { idxSeen.set(id, { status: "indexing", phase: "clone", done: 0, t: performance.now() / 1000, rate: 0 }); }
function renderCodeInfo(c) {
  const pct = idxPct(c);
  $("cvInfo").innerHTML = c.status === "indexing"
    ? `${esc(idxText(c))}<span class="idxbar"><i style="width:${Math.round((pct || 0) * 100)}%"></i></span>`
    : esc(c.status === "error" ? c.message || "Erreur" : `${code.files.length} fichiers · ${c.source || ""}`);
}

function renderLibrary() {
  const list = $("libCols");
  list.innerHTML = "";
  for (const c of library.collections) {
    const b = document.createElement("button");
    b.className = "lib-col" + (c.id === libSel ? " on" : "");
    const st = c.status === "indexing" ? '<span class="spin"></span>' : c.status === "error" ? '<span class="err">!</span>' : "";
    b.innerHTML = `${icon(c.kind === "code" ? "code" : "folder")}<span class="n">${esc(c.name)}</span>${st}<span class="c">${c.documents}</span>`;
    b.onclick = () => { libSel = c.id; renderLibrary(); };
    list.appendChild(b);
  }
  renderCollection();
}

async function renderCollection() {
  const box = $("libMain");
  const c = library.collections.find((x) => x.id === libSel);
  if (!c) { box.innerHTML = '<div class="side-empty">Aucune collection.</div>'; return; }
  let d;
  try { d = await getJSON(`/api/library/collections/${c.id}/documents`); } catch { return; }
  const isCode = c.kind === "code";
  box.innerHTML = `
    <div class="lib-head">
      <div><h2>${esc(c.name)}</h2>
        <p>${isCode ? `Projet de code · ${esc(c.source || "")}` : "Documents"} · ${d.documents.length} fichier${d.documents.length > 1 ? "s" : ""} · ${c.chunks} passage${c.chunks > 1 ? "s" : ""} indexé${c.chunks > 1 ? "s" : ""}</p>
        ${c.message || c.status === "indexing" ? `<p class="${c.status === "error" ? "lib-err" : ""}">${esc(idxText(c))}${c.status === "indexing" ? `<span class="idxbar"><i style="width:${Math.round((idxPct(c) || 0) * 100)}%"></i></span>` : ""}</p>` : ""}
      </div>
      <div class="row">
        ${isCode ? `<button class="btn" data-a="sync">${icon("refresh")} Mettre à jour</button>` : ""}
        <button class="btn" data-a="ask">${icon("spark")} Poser une question</button>
        <button class="iconbtn" data-a="rename" title="Renommer">${icon("edit")}</button>
        <button class="iconbtn" data-a="del" title="Supprimer la collection">${icon("trash")}</button>
      </div>
    </div>
    ${isCode ? "" : `<label class="drop-zone" id="libDrop">${icon("download")}<b>Dépose tes documents ici</b><span>ou clique pour choisir · PDF, Word, texte, Markdown, HTML, CSV…</span><input type="file" multiple hidden id="libFile"></label>`}
    <table class="lib-table"><thead><tr><th>${isCode ? "Fichier" : "Document"}</th><th>${isCode ? "Taille" : "Pages"}</th><th>Passages</th><th></th></tr></thead><tbody></tbody></table>`;
  const tb = box.querySelector("tbody");
  if (!d.documents.length) tb.innerHTML = `<tr><td colspan="4" class="none">${isCode ? "Indexation en cours…" : "Aucun document pour l'instant."}</td></tr>`;
  for (const doc of d.documents.slice(0, 400)) {
    const tr = document.createElement("tr");
    const status = doc.status === "indexing" ? '<span class="spin"></span> lecture…' : doc.status === "error" ? `<span class="lib-err" title="${esc(doc.message || "")}">${esc((doc.message || "erreur").slice(0, 60))}</span>` : doc.chunks;
    tr.innerHTML = `<td class="nm"><div>${icon(isCode ? "code" : "doc")}<span>${esc(isCode ? doc.path : doc.name)}</span></div></td><td>${isCode ? fmtBytes(doc.size) : (doc.pages || "—")}</td><td>${status}</td><td class="act"></td>`;
    const act = tr.querySelector(".act");
    const v = document.createElement("button"); v.className = "iconbtn"; v.title = "Aperçu"; v.innerHTML = icon("search");
    v.onclick = () => previewDoc(doc.id);
    act.appendChild(v);
    if (!isCode) {
      const dl = document.createElement("a"); dl.className = "iconbtn"; dl.title = "Télécharger"; dl.href = `/api/library/documents/${doc.id}/file`; dl.innerHTML = icon("download");
      const del = document.createElement("button"); del.className = "iconbtn"; del.title = "Supprimer"; del.innerHTML = icon("trash");
      del.onclick = async () => { if (!confirm(`Supprimer « ${doc.name} » de la bibliothèque ?`)) return; await send_(`/api/library/documents/${doc.id}`, "DELETE"); loadLibrary(); };
      act.append(dl, del);
    }
    tb.appendChild(tr);
  }
  if (d.documents.length > 400) tb.insertAdjacentHTML("beforeend", `<tr><td colspan="4" class="none">… et ${d.documents.length - 400} autres fichiers</td></tr>`);
  box.querySelector('[data-a="del"]').onclick = async () => {
    if (!confirm(`Supprimer la collection « ${c.name} » et tout son index ?`)) return;
    await send_(`/api/library/collections/${c.id}`, "DELETE"); libSel = null; loadLibrary();
  };
  box.querySelector('[data-a="rename"]').onclick = async () => {
    const n = prompt("Nouveau nom", c.name); if (!n?.trim()) return;
    await send_(`/api/library/collections/${c.id}`, "PATCH", { name: n.trim(), kind: c.kind }); loadLibrary();
  };
  box.querySelector('[data-a="ask"]').onclick = () => { setScope(String(c.id)); showView("chat"); newConversation(); fillInput(isCode ? "Explique-moi l'architecture de ce projet." : "Que contiennent ces documents ? "); };
  box.querySelector('[data-a="sync"]')?.addEventListener("click", async () => { await send_(`/api/library/collections/${c.id}/sync`, "POST"); markIndexing(c.id); toast("Mise à jour du projet lancée."); loadLibrary(); });
  const drop = $("libDrop");
  if (drop) {
    $("libFile").onchange = (e) => { uploadDocs(c.id, [...e.target.files]); e.target.value = ""; };
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("over"));
    drop.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.remove("over"); $("drop").classList.remove("on"); uploadDocs(c.id, [...e.dataTransfer.files]); });
  }
}

async function uploadDocs(cid, files) {
  for (const f of files) {
    if (f.size > 100 * 1024 * 1024) { toast(`<b>${esc(f.name)}</b> · trop gros (100 Mo max)`); continue; }
    try {
      const r = await fetch(`/api/library/collections/${cid}/documents?name=${encodeURIComponent(f.name)}`, { method: "POST", body: f, headers: { "Content-Type": "application/octet-stream", "X-Atom": "1" } });
      if (!r.ok) throw new Error((await r.json()).detail || "échec");
      entity.feedColor = [235, 235, 240]; entity.feeding = true;
      setTimeout(() => { entity.feeding = false; entity.feedColor = [110, 170, 255]; }, 2500);
    } catch (e) { toast(`<b>${esc(f.name)}</b> · ${esc(e.message)}`); }
  }
  toast(`<b>${files.length} document${files.length > 1 ? "s" : ""}</b> ajouté${files.length > 1 ? "s" : ""} · Atom les lit…`);
  loadLibrary();
}

$("libNewDocs").onclick = async () => {
  const n = prompt("Nom de la collection (ex. Administratif, Travail, Homelab)"); if (!n?.trim()) return;
  const c = await (await send_("/api/library/collections", "POST", { name: n.trim(), kind: "docs" })).json();
  libSel = c.id; loadLibrary();
};
$("libNewCode").onclick = () => {
  $("codeDlg").classList.add("open");
  const sel = $("codeServer");
  sel.innerHTML = library.server_projects.length ? library.server_projects.map((p) => `<option>${esc(p)}</option>`).join("") : '<option value="">(aucun dossier dans /projects)</option>';
  $("codeUrl").value = ""; $("codeName").value = "";
  $("codeUrl").focus();
};
$("codeCancel").onclick = () => $("codeDlg").classList.remove("open");
$("codeOk").onclick = async () => {
  const url = $("codeUrl").value.trim(), srv = $("codeServer").value;
  const source = url || srv;
  if (!source) { toast("Indique une adresse GitHub ou choisis un dossier du serveur."); return; }
  const name = $("codeName").value.trim() || source.replace(/\.git$/, "").split("/").filter(Boolean).pop();
  try {
    const c = await (await send_("/api/library/collections", "POST", { name, kind: "code", source })).json();
    $("codeDlg").classList.remove("open"); libSel = c.id; markIndexing(c.id); toast("Projet ajouté · téléchargement puis indexation, je te préviens quand c'est prêt."); loadLibrary();
  } catch (e) { toast(esc(e.message)); }
};

/* Aperçu d'un document : tous ses passages, celui cité mis en évidence */
async function previewDoc(did, chunkId) {
  let d;
  try { d = await getJSON(`/api/library/documents/${did}`); } catch { toast("Document introuvable (supprimé ?)."); return; }
  $("pvTitle").textContent = d.document.path && !d.document.path.startsWith("/") ? d.document.path : d.document.name;
  const body = $("pvBody");
  body.innerHTML = "";
  for (const ch of d.chunks) {
    const el = document.createElement("div");
    el.className = "pv-chunk" + (ch.id === chunkId ? " hit" : "");
    const where = ch.page ? `page ${ch.page}` : ch.line_start ? `lignes ${ch.line_start}-${ch.line_end}` : `passage ${ch.ord + 1}`;
    el.innerHTML = `<small>${where}</small>`;
    const pre = document.createElement(ch.line_start ? "pre" : "div");
    if (ch.line_start) pre.innerHTML = highlight(ch.text.replace(/^# .*\n/, "")); else pre.textContent = ch.text;
    el.appendChild(pre);
    body.appendChild(el);
  }
  if (!d.chunks.length) body.innerHTML = `<p class="note">${esc(d.document.message || "Pas encore indexé.")}</p>`;
  $("preview").classList.add("open");
  requestAnimationFrame(() => body.querySelector(".hit")?.scrollIntoView({ block: "center" }));
}
$("pvClose").onclick = () => $("preview").classList.remove("open");
$("preview").addEventListener("click", (e) => { if (e.target.id === "preview") $("preview").classList.remove("open"); });

/* Portée de la conversation : quelles collections Atom consulte */
function scopeLabel() {
  if (scope === "auto") return "Documents";
  if (scope === "none") return "Sans bibliothèque";
  const ids = scope.split(",").map(Number);
  const names = library.collections.filter((c) => ids.includes(c.id)).map((c) => c.name);
  return names.length ? names.join(", ") : "Documents";
}
function setScope(v) { scope = v; store.set("scope", v); renderScope(); }
function renderScope() {
  $("scopeBtn").innerHTML = icon(scope !== "auto" && scope !== "none" && library.collections.find((c) => String(c.id) === scope)?.kind === "code" ? "code" : "folder") + `<span>${esc(scopeLabel())}</span>`;
  $("scopeBtn").classList.toggle("on", scope !== "auto" && scope !== "none");
}
$("scopeBtn").onclick = (e) => {
  e.stopPropagation();
  const m = $("scopeMenu");
  if (m.classList.toggle("open")) {
    const ids = scope.split(",");
    m.innerHTML = `<button data-v="auto">${icon("folder")}<span><b>Documents</b><small>Atom consulte tes documents quand c'est utile</small></span></button>
      <button data-v="none">${icon("x")}<span><b>Sans bibliothèque</b><small>Ne rien consulter</small></span></button>
      <div class="sep"></div>` + library.collections.map((c) =>
      `<button data-v="${c.id}" class="${ids.includes(String(c.id)) ? "on" : ""}">${icon(c.kind === "code" ? "code" : "folder")}<span><b>${esc(c.name)}</b><small>${c.kind === "code" ? "Projet de code" : "Collection"} · ${c.documents} fichier${c.documents > 1 ? "s" : ""}</small></span></button>`).join("")
      + `<div class="sep"></div><button data-v="manage">${icon("settings")}<span><b>Gérer la bibliothèque…</b></span></button>`;
    m.querySelectorAll("button").forEach((b) => b.onclick = () => {
      m.classList.remove("open");
      if (b.dataset.v === "manage") return showView("library");
      setScope(b.dataset.v);
    });
  }
};
document.addEventListener("click", () => $("scopeMenu").classList.remove("open"));

function docsEl(refs) {
  const d = document.createElement("div");
  d.className = "sources";
  for (const r of refs) {
    const b = document.createElement("button");
    b.className = "src-l";
    b.innerHTML = `<i>D${r.n}</i><span>${esc(r.label)}</span><small>${esc(r.collection)}</small>`;
    b.onclick = () => previewDoc(r.document_id, r.chunk_id);
    d.appendChild(b);
  }
  return d;
}

/* ============================================================
   MODE HYBRIDE (local / auto / Mistral)
   ============================================================ */
let hybridState = null;
let engine = store.get("engine", "default");
const ENGINE_LABEL = () => ({ default: "Par défaut", local: "Local", auto: "Auto", mistral: hybridState?.name || "Mistral" });
function renderEngine() {
  const wrap = $("engineWrap");
  wrap.style.display = hybridState?.configured ? "" : "none";
  if (!hybridState) return;
  const eff = engine === "default" ? hybridState.mode : engine;
  const lbl = engine === "default" ? `${ENGINE_LABEL()[eff]}` : ENGINE_LABEL()[engine];
  $("engineBtn").innerHTML = icon(eff === "local" ? "orb" : "spark") + `<span>${esc(lbl)}</span>`;
  $("engineBtn").classList.toggle("on", eff !== "local");
}
function setEngine(v) { engine = v; store.set("engine", v); renderEngine(); }
$("engineBtn").onclick = (e) => {
  e.stopPropagation();
  const m = $("engineMenu");
  if (!m.classList.toggle("open")) return;
  const n = hybridState?.name || "Mistral";
  const opts = [
    ["default", "orb", `Par défaut (${ENGINE_LABEL()[hybridState.mode]})`, "Le réglage choisi dans Réglages → Hybride"],
    ["local", "orb", "Local", "Tout reste sur ton serveur"],
    ["auto", "spark", "Auto", `${n} pour les demandes complexes, local sinon`],
    ["mistral", "spark", n, `Toujours ${n} (dans les limites de confidentialité)`],
  ];
  m.innerHTML = opts.map(([v, ic, t, d]) => `<button data-v="${v}" class="${engine === v ? "on" : ""}">${icon(ic)}<span><b>${esc(t)}</b><small>${esc(d)}</small></span></button>`).join("")
    + `<div class="sep"></div><button data-v="settings">${icon("settings")}<span><b>Réglages du mode hybride…</b></span></button>`;
  m.querySelectorAll("button").forEach((b) => b.onclick = () => { m.classList.remove("open"); b.dataset.v === "settings" ? openSettings("hybrid") : setEngine(b.dataset.v); });
};
document.addEventListener("click", () => $("engineMenu").classList.remove("open"));

async function loadHybrid() {
  try { hybridState = await getJSON("/api/hybrid"); } catch { return; }
  renderEngine();
  const h = hybridState;
  $("hySetup").style.display = h.configured ? "none" : "";
  $("hySetup").innerHTML = "Aucun fournisseur distant configuré : ajoute une clé (Groq, Cerebras, Gemini…) dans le fichier <code>.env</code> du serveur — <code>ATOM_REMOTE_API_KEY=…</code> ou <code>ATOM_PROVIDERS=…</code> — puis relance Atom. Voir le README.";
  $("hyMode").innerHTML = "";
  for (const [v, t] of [["local", "Local"], ["auto", "Auto"], ["mistral", "Distant"]]) {
    const b = document.createElement("button");
    b.className = "btn" + (h.mode === v ? " primary" : "");
    b.textContent = t; b.disabled = !h.configured && v !== "local";
    b.onclick = () => saveHybrid({ mode: v });
    $("hyMode").appendChild(b);
  }
  $("hyMem").checked = h.allow_memory; $("hyDocs").checked = h.allow_docs; $("hyWeb").checked = h.allow_web;
  const box = $("hyProviders");
  box.innerHTML = h.providers.length ? "" : '<p class="note">Aucun fournisseur configuré.</p>';
  for (const p of h.providers) {
    const row = document.createElement("div");
    row.className = "prov" + (p.id === h.provider ? " on" : "");
    const pct = Math.min(100, (100 * p.used_today) / Math.max(1, p.limit));
    row.innerHTML = `<div class="prov-top"><label class="prov-main"><input type="radio" name="hyPrimary" ${p.id === h.provider ? "checked" : ""}> <b>${esc(p.name)}</b></label>
        <span class="prov-tags"><span>${esc(p.family)}</span><span title="Force estimée (1 à 3)">${"●".repeat(p.strength)}${"○".repeat(3 - p.strength)}</span>${p.private ? "" : "<span>sans données privées</span>"}${p.paused ? "<span>en pause</span>" : ""}</span></div>
      <div class="row prov-model"><select class="field"><option value="${esc(p.model)}">${esc(p.model)}</option><option value="__other">Autre… (saisir un nom)</option></select><input class="field" hidden value="${esc(p.model)}" spellcheck="false" autocomplete="off" placeholder="nom exact du modèle"><button class="btn sm">Enregistrer</button></div>
      <p class="note prov-note" hidden></p>
      <div class="metric"><div class="l"><span>${p.used_today} / ${p.limit} aujourd'hui</span><span></span></div><div class="bar"><i style="width:${pct}%"></i></div></div>`;
    row.querySelector("input").onchange = () => saveHybrid({ provider: p.id });
    const sel = row.querySelector("select"), inp = row.querySelector(".prov-model input"), note = row.querySelector(".prov-note");
    const showNote = (t) => { note.textContent = t; note.hidden = !t; };
    sel.onchange = () => { const other = sel.value === "__other"; inp.hidden = !other; sel.hidden = other; if (other) { inp.focus(); inp.select(); } };
    (async () => {   // liste chargée tout de suite, pour que le menu soit complet à l'ouverture
      try {
        const { models } = await getJSON(`/api/hybrid/models?provider=${encodeURIComponent(p.id)}`);
        if (!models.length) { showNote(`${p.name} ne publie pas de liste : choisis « Autre… » pour écrire le nom exact.`); return; }
        const missing = !models.includes(p.model);
        sel.innerHTML = (missing ? `<option value="${esc(p.model)}">${esc(p.model)} (introuvable)</option>` : "")
          + models.map((m) => `<option value="${esc(m)}" ${m === p.model ? "selected" : ""}>${esc(m)}</option>`).join("")
          + '<option value="__other">Autre… (saisir un nom)</option>';
        if (missing) showNote(`« ${p.model} » n'est plus proposé par ${p.name} : choisis un modèle dans la liste (${models.length} disponibles).`);
      } catch { showNote(`Liste des modèles indisponible : choisis « Autre… » pour écrire le nom exact.`); }
    })();
    row.querySelector("button").onclick = async () => {
      const model = (sel.hidden ? inp.value : sel.value).trim();
      if (!model || model === "__other") { inp.focus(); return; }
      try { hybridState = await (await api(`/api/hybrid/providers/${p.id}`, { method: "PUT", body: JSON.stringify({ model }) })).json(); toast(`${esc(p.name)} · modèle <b>${esc(model)}</b>`); }
      catch (e) { toast(esc(e.message)); }
      loadHybrid();
    };
    box.appendChild(row);
  }
  for (const x of h.skipped || []) box.insertAdjacentHTML("beforeend", `<div class="prov off"><div class="prov-top"><b style="font-weight:500">${esc(x.name)}</b><span class="prov-tags"><span>ignoré</span></span></div><p class="note" style="margin:6px 0 0">${esc(x.reason)} dans .env, puis <code>docker compose up -d atom</code>.</p></div>`);
  if (!h.providers_env) box.insertAdjacentHTML("beforeend", '<p class="note">Aucun fournisseur supplémentaire : ajoute par exemple <code>ATOM_CEREBRAS_API_KEY=…</code> dans <code>.env</code>, puis <code>docker compose up -d atom</code>.</p>');
}
async function saveHybrid(patch) {
  try { hybridState = await (await api("/api/hybrid", { method: "PUT", body: JSON.stringify(patch) })).json(); } catch (e) { toast(esc(e.message)); }
  loadHybrid();
}
$("hyMem").onchange = () => saveHybrid({ allow_memory: $("hyMem").checked });
$("hyDocs").onchange = () => saveHybrid({ allow_docs: $("hyDocs").checked });
$("hyWeb").onchange = () => saveHybrid({ allow_web: $("hyWeb").checked });

/* ============================================================
   MODE CODE — parcourir un projet, lire ses fichiers
   ============================================================ */
const code = { project: null, files: [], open: [], active: null, sel: null, proposal: null, editRange: null, changes: null, expanded: new Set([""]), grep: false };
const LANG = (p) => {
  const n = p.toLowerCase(), ext = n.includes(".") ? n.split(".").pop() : n.split("/").pop();
  return ({ py: "py", sh: "sh", bash: "sh", zsh: "sh", yml: "yaml", yaml: "yaml", toml: "toml", ini: "ini", cfg: "ini", conf: "ini", env: "ini",
    rb: "rb", js: "js", mjs: "js", cjs: "js", jsx: "js", ts: "js", tsx: "js", vue: "html", svelte: "html", json: "json",
    c: "c", h: "c", cpp: "c", hpp: "c", cc: "c", cs: "c", java: "c", kt: "c", go: "c", rs: "c", swift: "c", dart: "c", scala: "c", php: "c",
    css: "css", scss: "css", sass: "css", less: "css", html: "html", htm: "html", xml: "html", svg: "html",
    sql: "sql", lua: "sql", hs: "sql", md: "md", markdown: "md", dockerfile: "sh", makefile: "sh", tf: "sh", hcl: "sh", nix: "sh", r: "sh" })[ext] || "txt";
};
const COMMENT = { py: "#", sh: "#", yaml: "#", toml: "#", ini: "[#;]", rb: "#", js: "//", c: "//", css: null, sql: "--", json: null, html: null, md: null, txt: null };

/* Coloration par langage : commentaires, chaînes, nombres, mots-clés, fonctions, décorateurs, balises. */
function highlightLang(src, lang) {
  if (lang === "txt" || lang === "md") return esc(src);
  const lc = COMMENT[lang];
  const parts = [];
  if (lang === "html") parts.push("(<!--[\\s\\S]*?-->)");
  else if (["js", "c", "css"].includes(lang)) parts.push("(\\/\\*[\\s\\S]*?\\*\\/" + (lc ? "|" + lc + "[^\\n]*" : "") + ")");
  else if (lc) parts.push("(" + lc + "[^\\n]*)");
  else parts.push("(\\u0000)");
  parts.push(lang === "py" ? "(\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''|\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*')"
    : "(\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*'|`(?:\\\\.|[^`\\\\])*`)");
  parts.push("\\b(\\d+(?:\\.\\d+)?)\\b");
  parts.push(lang === "html" ? "(<\\/?[A-Za-z][\\w-]*|\\/?>)" : lang === "css" ? "(#[0-9a-fA-F]{3,8}\\b|@[\\w-]+)" : "(@[A-Za-z_][\\w.]*)");
  parts.push("\\b([A-Za-z_]\\w*)(?=\\s*\\()");
  parts.push("\\b([A-Za-z_][\\w-]*)\\b");
  const re = new RegExp(parts.join("|"), "g");
  let out = "", last = 0, m;
  while ((m = re.exec(src))) {
    if (!m[0]) { re.lastIndex++; continue; }
    out += esc(src.slice(last, m.index));
    const [tok, com, str, num, deco, fn, word] = m;
    if (com && com !== "\u0000") out += `<span class="tk-c">${esc(com)}</span>`;
    else if (str) out += `<span class="tk-s">${esc(str)}</span>`;
    else if (num) out += `<span class="tk-n">${num}</span>`;
    else if (deco) out += `<span class="tk-d">${esc(deco)}</span>`;
    else if (fn) out += KW.has(fn) ? `<span class="tk-k">${fn}</span>` : `<span class="tk-f">${fn}</span>`;
    else if (word) out += KW.has(word) ? `<span class="tk-k">${word}</span>` : (lang === "json" || lang === "yaml") && /^[A-Za-z]/.test(word) && src[m.index + word.length] === ":" ? `<span class="tk-f">${word}</span>` : esc(word);
    else out += esc(tok);
    last = m.index + tok.length;
  }
  return out + esc(src.slice(last));
}

// État du mode Code conservé entre deux chargements (F5) : projet, onglets, fichier actif, agent ouvert.
let codeRestored = false;
function saveCodeState() {
  if (!codeRestored) return;
  store.set("codeState", { project: code.project, open: code.open.map((f) => f.path), active: code.active, pane: cvPane });
}
async function loadCodeProjects() {
  try { library = await getJSON("/api/library"); } catch { return; }
  const projects = library.collections.filter((c) => c.kind === "code");
  const saved = !codeRestored ? store.get("codeState", null) : null;
  if (saved && projects.some((p) => p.id === saved.project)) code.project = saved.project;
  const sel = $("cvProject");
  sel.innerHTML = projects.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
  $("cvEmpty").hidden = projects.length > 0;
  $("cvMainWrap").hidden = projects.length === 0;
  if (!projects.length) return;
  if (!projects.some((p) => p.id === code.project)) code.project = projects[0].id;
  sel.value = code.project;
  await loadCodeFiles();
  if (saved && saved.project === code.project && !code.open.length) {
    for (const path of (saved.open || []).slice(-8)) if (code.files.some((f) => f.path === path)) await openFile(path);
    if (saved.pane) cvSetPane(saved.pane);
    if (saved.active && code.open.some((f) => f.path === saved.active)) { code.active = saved.active; renderTabs(); renderEditor(); renderTree(); }
    else { codeRestored = true; agOpen(); }
    codeRestored = true;
  } else if (!code.open.length) agOpen();
  codeRestored = true;
  if (projects.some((p) => p.status === "indexing")) { clearTimeout(libTimer); libTimer = setTimeout(loadLibrary, 2000); }
}
$("cvProject").onchange = async () => { if (!$("cvAgentView").hidden) agClose(); agRun = null; $("agLog").innerHTML = ""; $("agRes").hidden = true; code.project = +$("cvProject").value; code.open = []; code.proposal = null; code.gitSel = null; code.gitKnown = null; code.active = "__agent"; code.expanded = new Set([""]); await loadCodeFiles(); renderTabs(); renderEditor(); agOpen(); saveCodeState(); };

async function loadCodeFiles() {
  const d = await getJSON(`/api/library/collections/${code.project}/documents`);
  loadChanges(); loadSandbox();
  code.files = d.documents.map((x) => ({ path: x.path, size: x.size })).sort((a, b) => a.path.localeCompare(b.path));
  const c = d.collection;
  renderCodeInfo({ ...c, progress: library.collections.find((x) => x.id === c.id)?.progress });
  renderTree();
}

function renderTree() {
  const box = $("cvTree");
  const q = $("cvFilter").value.trim().toLowerCase();
  box.innerHTML = "";
  if (code.grep && q.length >= 2) return runGrep(q);
  if (q) {
    for (const f of code.files.filter((f) => f.path.toLowerCase().includes(q)).slice(0, 300)) box.appendChild(fileRow(f.path, f.path, 0));
    if (!box.children.length) box.innerHTML = '<div class="side-empty">Aucun fichier.</div>';
    return;
  }
  // arbre : dossiers repliables
  const tree = {};
  for (const f of code.files) {
    const parts = f.path.split("/");
    let node = tree;
    parts.forEach((p, i) => { if (i === parts.length - 1) (node.__files ||= []).push(f.path); else node = (node[p] ||= {}); });
  }
  const walk = (node, prefix, depth) => {
    for (const k of Object.keys(node).filter((k) => k !== "__files").sort()) {
      const path = prefix ? `${prefix}/${k}` : k;
      const open = code.expanded.has(path);
      const r = document.createElement("button");
      r.className = "cv-row dir"; r.style.paddingLeft = 8 + depth * 14 + "px";
      r.innerHTML = `<span class="car">${open ? "▾" : "▸"}</span>${icon("folder")}<span>${esc(k)}</span>`;
      r.onclick = () => { open ? code.expanded.delete(path) : code.expanded.add(path); renderTree(); };
      box.appendChild(r);
      if (open) walk(node[k], path, depth + 1);
    }
    for (const p of (node.__files || []).sort()) box.appendChild(fileRow(p, p.split("/").pop(), depth));
  };
  walk(tree, "", 0);
}
function fileRow(path, label, depth) {
  const r = document.createElement("button");
  r.className = "cv-row" + (code.active === path ? " on" : "");
  r.style.paddingLeft = 22 + depth * 14 + "px";
  r.title = path;
  r.innerHTML = `${icon("doc")}<span>${esc(label)}</span>`;
  r.onclick = () => openFile(path);
  return r;
}
async function runGrep(q) {
  const box = $("cvTree");
  box.innerHTML = '<div class="side-empty"><span class="spin"></span> Recherche…</div>';
  let r;
  try { r = await getJSON(`/api/library/collections/${code.project}/grep?q=${encodeURIComponent(q)}`); } catch { return; }
  box.innerHTML = r.matches.length ? "" : '<div class="side-empty">Aucun résultat.</div>';
  for (const m of r.matches) {
    const b = document.createElement("button");
    b.className = "cv-hit";
    const i = m.text.toLowerCase().indexOf(q);
    const t = i >= 0 ? esc(m.text.slice(0, i)) + `<mark>${esc(m.text.slice(i, i + q.length))}</mark>` + esc(m.text.slice(i + q.length)) : esc(m.text);
    b.innerHTML = `<small>${esc(m.path)}:${m.line}</small><code>${t}</code>`;
    b.onclick = () => openFile(m.path, m.line);
    box.appendChild(b);
  }
}
let grepTimer = 0;
$("cvFilter").addEventListener("input", () => { clearTimeout(grepTimer); grepTimer = setTimeout(renderTree, code.grep ? 300 : 0); });
$("cvGrep").onclick = () => { code.grep = !code.grep; $("cvGrep").classList.toggle("on", code.grep); $("cvFilter").placeholder = code.grep ? "Chercher dans le contenu…" : "Filtrer les fichiers…"; renderTree(); $("cvFilter").focus(); };

async function openFile(path, line) {
  let f = code.open.find((x) => x.path === path);
  if (!f) {
    try {
      const r = await getJSON(`/api/library/collections/${code.project}/file?path=${encodeURIComponent(path)}`);
      f = { path, content: r.content, md: false };
    } catch { toast("Fichier introuvable (projet à mettre à jour ?)."); return; }
    code.open.push(f);
    if (code.open.length > 8) code.open.shift();
  }
  code.active = path; code.sel = line ? [line, line] : null;
  renderTabs(); renderEditor(line); renderTree(); saveCodeState();
  entity.scan = true; clearTimeout(openFile._t); openFile._t = setTimeout(() => { entity.scan = false; }, 1400);
}
function closeTab(path) {
  code.open = code.open.filter((x) => x.path !== path);
  if (code.active === path) code.active = code.open.at(-1)?.path || "__agent";
  code.sel = null; renderTabs(); renderEditor(); renderTree(); saveCodeState();
}
function renderTabs() {
  const t = $("cvTabs");
  t.innerHTML = "";
  const home = document.createElement("div");
  home.className = "cv-tab home" + (code.active === "__agent" || !code.active ? " on" : "");
  home.title = "Agent : confier une tâche ou poser une question sur le projet";
  home.innerHTML = `${icon("spark")}<span>Agent</span>`;
  home.onclick = () => agOpen();
  t.appendChild(home);
  for (const f of code.open) {
    const b = document.createElement("div");
    b.className = "cv-tab" + (f.path === code.active ? " on" : "");
    b.title = f.path;
    b.innerHTML = `<span>${esc(f.path.split("/").pop())}</span>`;
    const x = document.createElement("button"); x.innerHTML = icon("x"); x.title = "Fermer";
    x.onclick = (e) => { e.stopPropagation(); closeTab(f.path); };
    b.onclick = () => { code.active = f.path; code.sel = null; renderTabs(); renderEditor(); renderTree(); };
    b.appendChild(x); t.appendChild(b);
  }
}
const MAX_LINES = 8000;
function renderEditor(scrollLine) {
  const isHome = code.active === "__agent" || !code.active;
  $("cvAgentView").hidden = !isHome; $("cvMainWrap").hidden = isHome;
  cvStatusUpdate();
  if (isHome) return;
  const f = code.open.find((x) => x.path === code.active);
  $("cvBar").hidden = !f; $("cvSelBar").hidden = true;
  if (code.proposal && code.proposal.path === f?.path) return renderDiff();
  $("cvDiffBar").hidden = true;
  const ed = $("cvEditor");
  if (!f) { ed.innerHTML = '<div class="cv-placeholder">Choisis un fichier dans l\'arborescence.<small>Clique sur les numéros de ligne (Maj+clic pour une plage) pour demander à Atom d\'expliquer un passage.</small></div>'; return; }
  const lines = f.content.split("\n");
  const shown = lines.slice(0, MAX_LINES);
  const lang = LANG(f.path);
  $("cvPath").textContent = f.path;
  $("cvMeta").textContent = `${lines.length} lignes · ${lang.toUpperCase()}`;
  $("cvMd").hidden = lang !== "md";
  $("cvMd").classList.toggle("on", f.md);
  if (lang === "md" && f.md) { ed.innerHTML = `<div class="cv-md md">${md(f.content)}</div>`; renderMath(ed); return; }
  ed.innerHTML = `<div class="cv-code"><div class="cv-gutter">${shown.map((_, i) => `<span data-l="${i + 1}">${i + 1}</span>`).join("")}</div><div class="cv-src"><div class="cv-hl" id="cvHl"></div><pre class="cv"><code>${highlightLang(shown.join("\n"), lang)}</code></pre></div></div>`
    + (lines.length > MAX_LINES ? `<div class="note" style="padding:10px 16px">Fichier long : seules les ${MAX_LINES} premières lignes sont affichées.</div>` : "");
  ed.querySelector(".cv-gutter").onclick = (e) => {
    const l = +e.target.dataset.l; if (!l) return;
    code.sel = e.shiftKey && code.sel ? [Math.min(code.sel[0], l), Math.max(code.sel[1], l)] : [l, l];
    paintSel();
  };
  paintSel(); cvStatusUpdate();
  if (scrollLine) requestAnimationFrame(() => { const lh = lineH(); ed.scrollTop = Math.max(0, (scrollLine - 6) * lh); });
}
const lineH = () => parseFloat(getComputedStyle(document.querySelector(".cv") || document.body).lineHeight) || 19;
function paintSel() {
  const hl = $("cvHl");
  if (!hl) return;
  document.querySelectorAll(".cv-gutter span.on").forEach((x) => x.classList.remove("on"));
  if (!code.sel) { hl.style.display = "none"; $("cvSelBar").hidden = true; return; }
  const [a, b] = code.sel, lh = lineH();
  Object.assign(hl.style, { display: "block", top: 12 + (a - 1) * lh + "px", height: (b - a + 1) * lh + "px" });
  for (let i = a; i <= b; i++) document.querySelector(`.cv-gutter span[data-l="${i}"]`)?.classList.add("on");
  $("cvSelBar").hidden = false;
  $("cvSelInfo").textContent = a === b ? `Ligne ${a}` : `Lignes ${a} à ${b}`;
}
function selectionText() {
  const f = code.open.find((x) => x.path === code.active);
  if (!f) return "";
  const [a, b] = code.sel || [1, f.content.split("\n").length];
  return f.content.split("\n").slice(a - 1, b).join("\n");
}
function askAtom(prompt, withSel) {
  const f = code.open.find((x) => x.path === code.active);
  if (!f) return;
  setScope(String(code.project));
  const [a, b] = code.sel || [];
  const name = withSel && code.sel ? `${f.path} (l. ${a}-${b})` : f.path;
  const text = withSel && code.sel ? selectionText() : f.content.slice(0, 12000);
  showView("chat"); newConversation();
  pending = [{ name, text }]; renderTray();
  fillInput(prompt);
}
$("cvExplain").onclick = () => askAtom("Explique-moi ces lignes : ce qu'elles font et pourquoi.", true);
$("cvReview").onclick = () => askAtom("Relis ces lignes : bugs possibles, cas oubliés, améliorations.", true);
$("cvAskSel").onclick = () => askAtom("", true);
$("cvAsk").onclick = () => askAtom("Explique-moi ce fichier : son rôle dans le projet et son fonctionnement.", false);
$("cvCopy").onclick = (e) => flashCopy(e.currentTarget, code.open.find((x) => x.path === code.active)?.content || "");
$("cvCopyPath").onclick = () => { copyText(code.active || ""); toast("Chemin copié."); };
$("cvMd").onclick = () => { const f = code.open.find((x) => x.path === code.active); if (f) { f.md = !f.md; renderEditor(); } };
$("cvSync").onclick = async () => { await send_(`/api/library/collections/${code.project}/sync`, "POST"); markIndexing(code.project); toast("Mise à jour du projet lancée."); loadLibrary(); };
$("cvAdd").onclick = () => { library.server_projects ||= []; $("libNewCode").onclick(); };
$("cvAdd2").onclick = () => $("cvAdd").onclick();

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

/* ---- agent : une tâche sur tout le projet, modifications validées à la fin */
let agRun = null;
const AG_ICON = { list: "folder", read: "doc", search: "search", edit: "edit", write: "plus", done: "check" };
function agOpen() {
  code.active = "__agent"; code.sel = null;
  renderTabs(); $("cvAgentView").hidden = false; $("cvMainWrap").hidden = true; cvStatusUpdate(); renderTree();
  const h = typeof hybridState !== "undefined" ? hybridState : null;
  const remoteOk = h?.configured && h?.allow_docs;
  $("agEngine").value = remoteOk ? "remote" : "local";
  $("agEngineNote").innerHTML = !h?.configured ? "Aucune API configurée : l'agent tournera en local (lent, moins fiable)."
    : !h.allow_docs ? 'Le code ne part pas vers l\'API tant que tu ne l\'autorises pas. <button class="btn sm" id="agAllow">Autoriser l\'envoi du code</button>' : "";
  $("agAllow")?.addEventListener("click", async () => {
    if (!confirm("Autoriser l'envoi de ta bibliothèque, de tes fichiers et de ton code aux API distantes ?\n\nSeuls les fournisseurs qui acceptent les données privées (pas Gemini ni OpenRouter) les recevront. Réglable dans Réglages → Connexions.")) return;
    await saveHybrid({ allow_docs: true }); agOpen(); toast("Envoi du code autorisé · l'agent utilisera l'API distante.");
  });
  $("agInfo").textContent = $("cvProject").selectedOptions[0]?.textContent || "";
  $("agClose").hidden = !code.open.length;
  loadAgHistory(); loadAgRules();
  const last = store.get(agKey(), null);
  if (last && (!agState || agState.id !== last)) agFollow(last, true);
  else if (!agRun) $("agTask").focus();
  saveCodeState();
}
function agClose() {
  const last = code.open.at(-1);
  if (!last) return;
  code.active = last.path; renderTabs(); renderEditor(); renderTree(); saveCodeState();
}
$("agClose").onclick = agClose;
$("agNew").onclick = () => { agReset(); agParent = null; $("agParentNote").hidden = true; store.set(agKey(), null); $("agTask").value = ""; $("agTask").focus(); loadAgHistory(); };
$("agParentCancel").onclick = () => { agParent = null; $("agParentNote").hidden = true; };
$("agTask").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("agRun").click(); });
function agStep(cls, ic, html) {
  const d = document.createElement("div"); d.className = "ag-step " + cls;
  d.innerHTML = `<span class="ic">${icon(ic)}</span><div>${html}</div>`;
  $("agLog").appendChild(d); $("agHome").hidden = true; d.scrollIntoView({ block: "nearest" });
  return d;
}
const agArgs = (t, a) => t === "read" ? `${a.path || ""}${a.start ? ` (l. ${a.start}${a.end ? "-" + a.end : ""})` : ""}` : t === "search" ? `« ${a.query || ""} »`
  : t === "list" ? (a.dir || "racine") : a.path || "";
const AG_VERB = { list: "Liste", read: "Lit", search: "Cherche", edit: "Modifie", write: "Écrit", done: "Terminé" };
// Les tâches tournent sur le serveur : la page ne fait que suivre (et peut être rechargée).
let agPoll = 0, agState = null;   // { id, after, first, lastAction, thinking }
const agKey = () => `agent:last:${code.project}`;
function agReset() { $("agLog").innerHTML = ""; $("agRes").hidden = true; agRun = null; agState = null; clearTimeout(agPoll); agHomeUpdate(); }
function agBusy(on) {
  const btn = $("agRun"); btn.textContent = on ? "Arrêter" : "Lancer"; btn.classList.toggle("primary", !on);
  if (on) { setEmotion("focus"); entity.scan = true; } else { setEmotion("idle"); entity.scan = false; }
}
function agHandle(ev, live) {
  const st = agState, proj = $("cvProject").selectedOptions[0]?.textContent || "";
  if (ev.type === "start") { $("agInfo").textContent = `${proj} · ${ev.info}`; agRun = { ...(agRun || {}), id: ev.id, writable: ev.writable }; }
  else if (ev.type === "engine") { $("agInfo").textContent = `${proj} · ${ev.name}`; }
  else if (ev.type === "thinking") { st.thinking?.remove(); st.thinking = live ? agStep("", "spark", '<span class="t"><span class="spin"></span> réfléchit…</span>') : null; if (live) entity.tokenKick = 1; }
  else if (ev.type === "thought") { st.thinking?.remove(); agStep("", "spark", `<span class="t">${esc(ev.text)}</span>`); }
  else if (ev.type === "action") {
    st.thinking?.remove();
    if (ev.thought) agStep(st.first ? "plan" : "", "spark", `<span class="t">${esc(ev.thought)}</span>`);
    st.first = false;
    if (ev.tool !== "done") {
      st.lastAction = agStep("", AG_ICON[ev.tool] || "spark", `<span class="a">${AG_VERB[ev.tool] || esc(ev.tool)} ${esc(agArgs(ev.tool, ev.args))}</span><div class="r"></div>`);
      st.lastAction.querySelector(".a").onclick = (e) => e.currentTarget.closest(".ag-step").classList.toggle("open");
      if (live && (ev.tool === "edit" || ev.tool === "write")) entity.absorb = 1;
    }
  } else if (ev.type === "result" && st.lastAction) {
    st.lastAction.querySelector(".r").textContent = ev.text; if (!ev.ok) st.lastAction.classList.add("ko");
  } else if (ev.type === "info") agStep("", "spark", `<span class="t">${esc(ev.message)}</span>`);
  else if (ev.type === "error") { st.thinking?.remove(); agStep("ko", "x", `<span class="t">${esc(ev.message)}</span>`); if (live) entity.glitch = 1; }
  else if (ev.type === "done") { st.thinking?.remove(); agRun = { ...(agRun || {}), id: ev.id, files: ev.files, summary: ev.summary, applied: ev.applied || [] }; agResults(); }
}
async function agFollow(rid, live = true) {
  clearTimeout(agPoll);
  if (!agState || agState.id !== rid) {
    $("agLog").innerHTML = ""; $("agRes").hidden = true;
    agState = { id: rid, after: 0, first: true };
  }
  let r;
  try { r = await getJSON(`/api/agent/runs/${rid}?after=${agState.after}`); }
  catch { agBusy(false); store.set(agKey(), null); return; }
  if (agState.after === 0) {
    agStep("plan", "users", `<span class="t"><b>${esc(r.task)}</b>${r.parent ? ' <span class="note">· suite d\'une tâche précédente</span>' : ""}</span>`);
  }
  for (const ev of r.events) agHandle(ev, live && r.status === "running");
  agState.after += r.events.length;
  const running = r.status === "running";
  agBusy(running);
  if (running) agPoll = setTimeout(() => agFollow(rid, true), 900);
  else {
    if (r.status === "interrupted") agStep("ko", "x", '<span class="t">Tâche interrompue par un redémarrage du serveur.</span>');
    if (r.status === "stopped" && !agRun?.files) agStep("ko", "x", '<span class="t">Arrêtée.</span>');
    loadAgHistory();
  }
}
$("agRun").onclick = async () => {
  if (agState && $("agRun").textContent === "Arrêter") { try { await send_(`/api/agent/runs/${agState.id}/stop`, "POST"); } catch {} return; }
  const task = $("agTask").value.trim();
  if (task.length < 3) { $("agTask").focus(); return; }
  agReset();
  try {
    const { id } = await (await send_(`/api/agent/${code.project}`, "POST", { task, engine: $("agEngine").value, parent: agParent || undefined })).json();
    const wasFollowUp = !!agParent;
    agParent = null; $("agParentNote").hidden = true;
    store.set(agKey(), id); agBusy(true); await agFollow(id);
    if (wasFollowUp || CORRECTION.test(task)) agSuggestRule(task);
  } catch (e) { toast(`<b>Agent</b> · ${esc(e.message)}`); }
};
let agParent = null;
async function loadAgHistory() {
  const sel = $("agHistory");
  let d; try { d = await getJSON(`/api/agent/${code.project}/runs`); } catch { return; }
  const ST = { running: "en cours", done: "terminée", error: "erreur", stopped: "arrêtée", interrupted: "interrompue" };
  agHomeUpdate(d.runs);
  sel.innerHTML = '<option value="">Historique…</option>' + d.runs.map((r) =>
    `<option value="${r.id}" ${agState?.id === r.id ? "selected" : ""}>${esc(new Date(r.created_at * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }))} · ${esc(r.task.slice(0, 60))} · ${ST[r.status] || r.status}${r.files ? ` · ${r.files} fichier(s)` : ""}</option>`).join("");
  sel.hidden = !d.runs.length;
}
$("agHistory").onchange = (e) => { const id = e.target.value; if (!id) return; agReset(); store.set(agKey(), id); agFollow(id, true); };
function agContinue() {
  agParent = agRun?.id || null;
  $("agParentNote").hidden = !agParent;
  $("agTask").value = ""; $("agTask").placeholder = "Que doit faire l'agent ensuite ? Ex. « Ajoute maintenant des tests pour Parse »";
  $("agTask").focus(); $("agForm").scrollIntoView({ block: "nearest" });
}
function agResults() {
  const box = $("agRes"), r = agRun; box.hidden = false;
  if (!r.files?.length) {
    box.innerHTML = (r.summary ? `<h5>Réponse de l'agent</h5><div class="sum md"></div>` : "<h5>Aucune modification proposée</h5>")
      + `<p class="note">${r.applied?.length ? `Appliqué : ${esc(r.applied.join(", "))}. Pense au commit dans le panneau Git.` : "Aucun fichier modifié."}</p><div class="ag-acts"><button class="btn" id="agMore">Poursuivre…</button></div>`;
    if (r.summary) setMd(box.querySelector(".sum"), r.summary);
    $("agMore").onclick = agContinue;
    return;
  }
  const add = r.files.reduce((s, f) => s + f.added, 0), rem = r.files.reduce((s, f) => s + f.removed, 0);
  box.innerHTML = `<h5>${r.files.length} fichier${r.files.length > 1 ? "s" : ""} modifié${r.files.length > 1 ? "s" : ""} · +${add} / −${rem}</h5>
    ${r.summary ? `<div class="sum md">${md(r.summary)}</div>` : ""}
    ${r.files.map((f, i) => `<details class="ag-file"><summary><input type="checkbox" data-ag="${i}" checked><span>${esc(f.path)}</span>${f.new_file ? "<em>nouveau</em>" : ""}<em>+${f.added} −${f.removed}</em></summary>
      <div class="cv-diff">${f.diff.split("\n").filter((l, k) => !(k < 2 && (l.startsWith("---") || l.startsWith("+++")))).map((l) => `<div class="${l.startsWith("@@") ? "hunk" : l[0] === "+" ? "add" : l[0] === "-" ? "del" : ""}">${esc(l)}</div>`).join("")}</div></details>`).join("")}
    <div class="ag-acts">${r.writable !== false ? '<button class="btn primary" id="agApply">Appliquer la sélection</button>' : '<span class="note">Projet en lecture seule : télécharge le patch.</span>'}
      <button class="btn" id="agPatch">${icon("download")}Patch</button>${sbInfo?.enabled ? '<button class="btn" id="agTest">Tester ces modifications</button>' : ""}<button class="btn" id="agMore">Poursuivre…</button><button class="btn" id="agDrop">Abandonner</button></div>`;
  $("agMore").onclick = agContinue;
  if ($("agTest")) $("agTest").onclick = () => { let o = box.querySelector(".sb-out"); if (!o) { o = document.createElement("div"); o.className = "sb-out"; box.appendChild(o); } sbRun({ run_id: r.id }, o, $("agTest")); };
  box.querySelectorAll(".ag-file input").forEach((c) => { c.onclick = (e) => e.stopPropagation(); });
  const picked = () => [...box.querySelectorAll("[data-ag]:checked")].map((c) => r.files[+c.dataset.ag]);
  $("agPatch").onclick = () => downloadPatch(picked().map((f) => f.diff).join(""), "atom-agent.patch");
  $("agDrop").onclick = async () => {
    if (!confirm("Abandonner ces modifications et effacer cette tâche de l'historique ?")) return;
    try { await send_(`/api/agent/runs/${r.id}`, "DELETE"); } catch {}
    store.set(agKey(), null); agReset(); loadAgHistory();
  };
  if ($("agApply")) $("agApply").onclick = async () => {
    const files = picked(); if (!files.length) { toast("Coche au moins un fichier."); return; }
    try {
      const d = await (await send_(`/api/agent/runs/${r.id}/apply`, "POST", { paths: files.map((f) => f.path) })).json();
      toast(`${d.applied.length} fichier${d.applied.length > 1 ? "s" : ""} appliqué${d.applied.length > 1 ? "s" : ""}` + (d.conflicts.length ? ` · ${d.conflicts.length} en conflit (modifiés entre-temps) : ${esc(d.conflicts.join(", "))}` : "") + ". Pense au commit dans le panneau Git.");
      entity.seal = 1;
      code.open = code.open.filter((x) => !d.applied.includes(x.path));
      r.files = r.files.filter((f) => !d.applied.includes(f.path));
      r.applied = [...(r.applied || []), ...d.applied];
      agResults(); loadChanges(); setTimeout(loadCodeFiles, 1500); saveCodeState();
    } catch (e) { toast(`<b>Agent</b> · ${esc(e.message)}`); }
  };
}

/* ---- bac à sable : lancer les tests dans un conteneur jetable */
let sbInfo = null;
async function loadSandbox() {
  try { sbInfo = await getJSON(`/api/sandbox/${code.project}`); } catch { sbInfo = null; $("cvTests").hidden = true; return; }
  $("cvTests").hidden = false;
  $("sbCmd").textContent = sbInfo.enabled ? (sbInfo.command || "commande à préciser") : "bac à sable désactivé";
  $("sbCmd").title = sbInfo.enabled ? sbInfo.command : sbInfo.reason;
  $("sbRun").hidden = !sbInfo.enabled; $("sbEdit").hidden = !sbInfo.enabled;
  if (!sbInfo.enabled) $("sbOut").innerHTML = `<div class="st">${esc(sbInfo.reason)} — voir le README, section « Bac à sable ».</div>`;
}
$("sbEdit").onclick = () => {
  const inp = $("sbCmdIn");
  if (inp.hidden) { inp.value = sbInfo?.command || ""; inp.hidden = false; $("sbCmd").hidden = true; inp.focus(); $("sbEdit").textContent = "enregistrer"; return; }
  send_(`/api/sandbox/${code.project}`, "PUT", { command: inp.value }).then((r) => r.json()).then((d) => { sbInfo = d; loadSandbox(); toast("Commande de test enregistrée."); }).catch((e) => toast(esc(e.message)));
  inp.hidden = true; $("sbCmd").hidden = false; $("sbEdit").textContent = "modifier";
};
$("sbCmdIn").addEventListener("keydown", (e) => { if (e.key === "Enter") $("sbEdit").click(); if (e.key === "Escape") { $("sbCmdIn").hidden = true; $("sbCmd").hidden = false; $("sbEdit").textContent = "modifier"; } });
async function sbRun(body, out, btn) {
  if (btn.disabled) return;
  const label = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Tests…';
  out.innerHTML = ""; setEmotion("focus"); entity.scan = true;
  const add = (cls, html) => { const d = document.createElement("div"); d.className = cls; d.innerHTML = html; out.appendChild(d); return d; };
  try {
    const r = await api(`/api/sandbox/${code.project}/run`, { method: "POST", body: JSON.stringify(body) });
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true }); let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === "step") add("st", esc(ev.message));
        else if (ev.type === "result") {
          out.querySelectorAll(".st").forEach((x) => x.remove());
          const ok = ev.code === 0;
          add("res " + (ok ? "ok" : "ko"), ok ? `✓ Tests réussis · ${ev.duration} s` : ev.code === -1 ? "Bac à sable indisponible" : `✗ Échec (code ${ev.code}) · ${ev.duration} s`);
          add("", `<pre>${esc((ev.output || "").replace(/\x1b\[[0-9;]*m/g, "") || "(aucune sortie)")}</pre>`);
          if (ok) entity.seal = 1; else entity.glitch = 1;
          if (ev.code !== -1 && !body.run_id) { sbLast = { ok }; cvStatusUpdate(); }
        }
      }
    }
  } catch (e) { add("res ko", esc(e.message)); }
  finally { btn.disabled = false; btn.innerHTML = label; setEmotion("idle"); entity.scan = false; }
}
$("sbRun").onclick = () => sbRun({}, $("sbOut"), $("sbRun"));

/* ---- barre d'activité, barre d'état, ouverture rapide (inspiré de VS Code / Zed) */
let cvPane = "files";
const PANE_NAMES = { files: "Fichiers", search: "Recherche dans le code", git: "Git", tests: "Tests" };
function cvSetPane(name) {
  cvPane = PANE_NAMES[name] ? name : "files";
  document.querySelector(".cv-side").dataset.show = cvPane;
  document.querySelectorAll("#cvRail button").forEach((b) => b.classList.toggle("on", b.dataset.pane === cvPane));
  $("cvPaneTitle").textContent = PANE_NAMES[cvPane];
  const grep = cvPane === "search";
  if (code.grep !== grep) { code.grep = grep; $("cvFilter").value = ""; }
  $("cvFilter").placeholder = grep ? "Texte à chercher dans tous les fichiers…" : "Filtrer par nom de fichier…";
  if (cvPane === "files" || cvPane === "search") { renderTree(); setTimeout(() => $("cvFilter").focus(), 0); }
  $("cvGitNote").hidden = !!code.git;
  saveCodeState();
}
document.querySelectorAll("#cvRail button").forEach((b) => { b.onclick = () => cvSetPane(b.dataset.pane); });
document.querySelector(".cv-side").dataset.show = "files";
let sbLast = null;   // dernier résultat de tests
function cvStatusUpdate() {
  const g = code.git;
  $("stBranch").innerHTML = g ? `<span class="lnk" data-go="git">⎇ ${esc(g.branch)}</span>` : "";
  const n = g?.files.length || 0;
  $("stChanges").innerHTML = g ? `<span class="lnk" data-go="git">${n ? `${n} modif.` : "propre"}${g.ahead ? ` · ↑${g.ahead}` : ""}</span>` : "";
  $("stTests").innerHTML = sbLast ? `<span class="lnk ${sbLast.ok ? "ok" : "ko"}" data-go="tests">${sbLast.ok ? "✓ tests" : "✗ tests"}</span>` : "";
  $("railGitDot").hidden = !n;
  $("railTestDot").hidden = !sbLast; $("railTestDot").classList.toggle("ko", !!sbLast && !sbLast.ok);
  const f = code.open.find((x) => x.path === code.active);
  $("stFile").textContent = f ? `${f.path} · ${f.content.split("\n").length} lignes · ${LANG(f.path).toUpperCase()}${code.sel ? ` · sél. ${code.sel[0]}-${code.sel[1]}` : ""}` : (code.active === "__agent" ? "Agent" : "");
  $("cvStatus").querySelectorAll("[data-go]").forEach((x) => { x.onclick = () => cvSetPane(x.dataset.go); });
}
// Ouverture rapide : recherche floue sur le nom et le chemin
let qoSel = 0, qoItems = [];
function qoScore(q, path) {
  const name = path.split("/").pop().toLowerCase(), p = path.toLowerCase();
  if (!q) return 1;
  if (name.startsWith(q)) return 100 - name.length / 100;
  if (name.includes(q)) return 80 - name.indexOf(q);
  if (p.includes(q)) return 50 - p.indexOf(q) / 10;
  let i = 0; for (const ch of p) if (ch === q[i]) i++;
  return i === q.length ? 20 - p.length / 100 : 0;
}
function qoRender() {
  const q = $("qoIn").value.trim().toLowerCase();
  const recent = code.open.map((f) => f.path).reverse();
  qoItems = (q ? code.files.map((f) => f.path) : [...new Set([...recent, ...code.files.map((f) => f.path)])])
    .map((p) => [p, qoScore(q, p) + (recent.includes(p) ? 5 : 0)]).filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 40).map((x) => x[0]);
  qoSel = Math.min(qoSel, Math.max(0, qoItems.length - 1));
  $("qoList").innerHTML = qoItems.map((p, i) => {
    const name = p.split("/").pop(), dir = p.slice(0, -name.length);
    const k = q ? name.toLowerCase().indexOf(q) : -1;
    const nm = k >= 0 ? esc(name.slice(0, k)) + `<b>${esc(name.slice(k, k + q.length))}</b>` + esc(name.slice(k + q.length)) : esc(name);
    return `<button data-i="${i}" class="${i === qoSel ? "on" : ""}"><span>${nm}</span><small>${esc(dir)}</small></button>`;
  }).join("") || '<p class="note" style="padding:8px">Aucun fichier.</p>';
  $("qoList").querySelectorAll("button").forEach((b) => { b.onclick = () => qoPick(+b.dataset.i); });
}
function qoOpen() { if (!code.project) return; $("quickOpen").hidden = false; $("qoIn").value = ""; qoSel = 0; qoRender(); $("qoIn").focus(); }
function qoClose() { $("quickOpen").hidden = true; }
function qoPick(i) { const p = qoItems[i]; qoClose(); if (p) openFile(p); }
$("qoIn").oninput = () => { qoSel = 0; qoRender(); };
$("qoIn").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { qoSel = Math.min(qoItems.length - 1, qoSel + 1); qoRender(); e.preventDefault(); }
  else if (e.key === "ArrowUp") { qoSel = Math.max(0, qoSel - 1); qoRender(); e.preventDefault(); }
  else if (e.key === "Enter") qoPick(qoSel);
  else if (e.key === "Escape") qoClose();
});
$("quickOpen").onclick = (e) => { if (e.target.id === "quickOpen") qoClose(); };
$("stQuick").onclick = qoOpen;
document.addEventListener("keydown", (e) => {
  if ($("codeView").hidden) return;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && !e.shiftKey && e.key.toLowerCase() === "p") { e.preventDefault(); qoOpen(); }
  else if (mod && e.shiftKey && e.key.toLowerCase() === "f") { e.preventDefault(); cvSetPane("search"); }
  else if (mod && e.shiftKey && e.key.toLowerCase() === "g") { e.preventDefault(); cvSetPane("git"); }
  else if (mod && e.key === "Enter" && code.active === "__agent" && document.activeElement !== $("agTask")) { e.preventDefault(); $("agTask").focus(); }
});
// Accueil de l'agent : idées de tâches et tâches récentes
const AG_IDEAS = [
  ["Expliquer le projet", "Explique-moi ce projet : à quoi il sert, son architecture, les fichiers clés et comment ils s'articulent."],
  ["Trouver des bugs", "Relis le code et trouve les bugs probables ou les cas non gérés. Pour chacun : fichier, ligne, risque, et propose une correction."],
  ["Ajouter des tests", "Ajoute des tests unitaires pour les fonctions principales qui n'en ont pas, puis lance-les."],
  ["Documenter", "Ajoute des commentaires de documentation sur les fonctions publiques qui n'en ont pas, sans changer le code."],
  ["Gestion des erreurs", "Repère les erreurs ignorées ou mal remontées et améliore leur gestion, sans changer le comportement normal."],
  ["Mettre à jour le README", "Mets à jour le README : présentation, installation, utilisation, structure du projet — d'après le code actuel."],
  ["Sécurité", "Fais une revue de sécurité du projet (entrées non validées, secrets, exécution de commandes, chemins) et propose des corrections."],
];
$("agChips").innerHTML = AG_IDEAS.map(([t], i) => `<button data-k="${i}">${esc(t)}</button>`).join("");
$("agChips").querySelectorAll("button").forEach((b) => { b.onclick = () => { $("agTask").value = AG_IDEAS[+b.dataset.k][1]; $("agTask").focus(); }; });
function agHomeUpdate(runs) {
  const showing = !!$("agLog").children.length;
  $("agHome").hidden = showing;
  if (!runs) return;
  const ST = { running: "en cours", done: "terminée", error: "erreur", stopped: "arrêtée", interrupted: "interrompue" };
  const list = runs.slice(0, 6);
  $("agRecentTitle").hidden = !list.length;
  $("agRecent").innerHTML = list.map((r) => `<button data-id="${r.id}"><span class="t">${esc(r.task)}</span><small>${ST[r.status] || r.status}</small>
    <small class="t">${esc(r.summary || "")}</small><small>${new Date(r.created_at * 1000).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })}${r.files ? ` · ${r.files} fichier(s)` : ""}</small></button>`).join("");
  $("agRecent").querySelectorAll("button").forEach((b) => { b.onclick = () => { agReset(); store.set(agKey(), b.dataset.id); agFollow(b.dataset.id, true); }; });
}

/* ---- règles retenues par projet (comme les règles de Cursor) */
let agRules = [];
async function loadAgRules() {
  try { agRules = (await getJSON(`/api/agent/${code.project}/rules`)).rules; } catch { agRules = []; }
  $("agRules").innerHTML = agRules.length ? agRules.map((r, i) => `<div><span>${esc(r)}</span><button data-rm="${i}" title="Supprimer">retirer</button></div>`).join("")
    : '<p class="note" style="margin:0">Aucune règle. Quand tu corriges l\'agent (« utilise plutôt… », « jamais… »), il te propose de la retenir.</p>';
  $("agRules").querySelectorAll("[data-rm]").forEach((b) => { b.onclick = () => saveAgRules(agRules.filter((_, i) => i !== +b.dataset.rm)); });
}
async function saveAgRules(list) {
  try { agRules = (await (await send_(`/api/agent/${code.project}/rules`, "PUT", { rules: list })).json()).rules; } catch (e) { toast(esc(e.message)); }
  loadAgRules();
}
$("agRuleAdd").onclick = () => { const v = $("agRuleIn").value.trim(); if (!v) return; $("agRuleIn").value = ""; saveAgRules([...agRules, v]); toast("Règle ajoutée au projet."); };
$("agRuleIn").addEventListener("keydown", (e) => { if (e.key === "Enter") $("agRuleAdd").click(); });
// Une correction ressemble souvent à une règle durable : on propose de la retenir.
const CORRECTION = /\b(toujours|jamais|ne (?:pas|plus|jamais)|n'utilise|utilise plutôt|plutôt que|au lieu de|on utilise|je préfère|préfère|évite|interdit|convention|style)\b/i;
function agSuggestRule(task) {
  const sentence = task.split(/(?<=[.!?])\s+/).find((x) => CORRECTION.test(x));
  if (!sentence || agRules.includes(sentence.trim())) return;
  const d = agStep("plan", "check", `<span class="t">Retenir comme règle du projet ? « ${esc(sentence.trim())} » <button class="btn sm" data-keep>Retenir</button></span>`);
  d.querySelector("[data-keep]").onclick = (e) => { saveAgRules([...agRules, sentence.trim()]); e.currentTarget.replaceWith(document.createTextNode("✓ retenue")); };
}

/* ============================================================
   ATELIER MULTI-IA
   ============================================================ */
let workshopCfg = null, workshopNext = false, remoteModels = [];
async function loadWorkshop() {
  try { workshopCfg = await getJSON("/api/workshop"); } catch { return; }
  $("wsBtn").style.display = workshopCfg.enabled ? "" : "none";
  if (!workshopCfg.enabled && workshopNext) { workshopNext = false; }
  $("wsBtn").classList.toggle("on", workshopNext);
  $("wsEnabled").checked = workshopCfg.enabled;
  $("wsPattern").innerHTML = "";
  for (const [k, label] of Object.entries(workshopCfg.patterns)) {
    const b = document.createElement("button");
    b.className = "btn" + (workshopCfg.pattern === k ? " primary" : "");
    b.textContent = label; b.onclick = () => saveWorkshop({ pattern: k });
    $("wsPattern").appendChild(b);
  }
  const opts = workshopCfg.options.map((o) => [o.id, o.label + (o.family ? ` · ${o.family}` : "")]);
  const roles = workshopCfg.roles[workshopCfg.pattern];
  $("wsParts").innerHTML = "";
  roles.forEach((role, i) => {
    const row = document.createElement("div"); row.className = "row"; row.style.margin = "6px 0";
    const cur = workshopCfg.participants[i] || "auto";
    row.innerHTML = `<span style="width:130px;font-size:13px;color:var(--text-2)">${esc(role)}</span>`;
    const sel = document.createElement("select"); sel.className = "field"; sel.style.cssText = "flex:1;min-width:0;max-width:260px";
    sel.innerHTML = opts.map(([v, t]) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(t)}</option>`).join("")
      + (opts.some(([v]) => v === cur) ? "" : `<option selected value="${esc(cur)}">${esc(cur)}</option>`);
    sel.onchange = () => { const p = [...workshopCfg.participants]; p[i] = sel.value; saveWorkshop({ participants: p }); };
    row.appendChild(sel);
    const eff = document.createElement("span"); eff.className = "note"; eff.style.cssText = "margin-left:8px;white-space:nowrap";
    if (cur === "auto") eff.textContent = "→ " + (workshopCfg.assigned[i] || "");
    row.appendChild(eff);
    $("wsParts").appendChild(row);
  });
  $("wsWarn").innerHTML = workshopCfg.warnings.map((w) => `⚠ ${esc(w)}`).join("<br>");
  $("wsWarn").hidden = !workshopCfg.warnings.length;
  $("wsRoundsRow").hidden = workshopCfg.pattern !== "review";
  $("wsRounds").value = workshopCfg.rounds;
  const n = workshopCfg.pattern === "review" ? 1 + 2 * workshopCfg.rounds : 3;
  const remote = (workshopCfg.pattern === "review"
    ? [workshopCfg.assigned[0], ...Array(workshopCfg.rounds).fill(0).flatMap(() => [workshopCfg.assigned[1], workshopCfg.assigned[2]])]
    : workshopCfg.assigned.slice(0, 3)).filter((p) => !p.startsWith("Local")).length;
  $("wsCost").textContent = `Jusqu'à ${n} étapes par demande, dont ${remote} via des API distantes. Compte jusqu'à ${n}× le temps d'une réponse normale`
    + (workshopCfg.pattern === "review" ? " — si la relecture ne trouve rien d'important, la correction est sautée." : ".");
}
async function saveWorkshop(patch) {
  try { await api("/api/workshop", { method: "PUT", body: JSON.stringify(patch) }); } catch (e) { toast(esc(e.message)); }
  loadWorkshop();
}
$("wsEnabled").onchange = () => saveWorkshop({ enabled: $("wsEnabled").checked });
$("wsRounds").onchange = () => saveWorkshop({ rounds: +$("wsRounds").value });
$("wsBtn").onclick = () => { workshopNext = !workshopNext; $("wsBtn").classList.toggle("on", workshopNext); input.focus(); };

function workshopEl(w) {
  const d = document.createElement("details");
  d.className = "ws";
  d.innerHTML = `<summary>${icon("users")}Atelier · ${esc(w.name)} · ${w.steps.length} étape${w.steps.length > 1 ? "s" : ""} avant la réponse</summary>`;
  for (const s of w.steps) {
    const c = document.createElement("div"); c.className = "ws-step";
    c.innerHTML = `<div class="ws-h"><b>${esc(s.role)}</b><span>${esc(s.engine)}</span></div><div class="md"></div>`;
    setMd(c.querySelector(".md"), s.text);
    d.appendChild(c);
  }
  return d;
}

async function sendWorkshop(text) {
  exitHero();
  workshopNext = false; $("wsBtn").classList.remove("on");
  $("empty")?.remove();
  setBusy(true);
  const userMsg = { role: "user", content: text };
  history.push(userMsg);
  chat.appendChild(msgEl(userMsg, history.length - 1));
  setEmotion("focus"); setEntityState("atelier…");
  const el = document.createElement("div");
  el.className = "msg atom";
  el.innerHTML = `<details class="ws" open><summary>${icon("users")}Atelier en cours…</summary><div class="ws-live"></div></details><div class="body md"></div>`;
  chat.appendChild(el); scroller.scrollTop = scroller.scrollHeight;
  const live = el.querySelector(".ws-live"), body = el.querySelector(".body"), sum = el.querySelector("summary");
  const steps = []; let final = "", asstId = null, q = false;
  controller = new AbortController();
  try {
    const r = await api("/api/workshop/run", { method: "POST", signal: controller.signal,
      body: JSON.stringify({ message: text, conversation_id: settings.conversationId }) });
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1);
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === "meta") { if (settings.conversationId !== ev.conversation_id) { settings.conversationId = ev.conversation_id; saveSettings(); loadConversations(); } }
        else if (ev.type === "ids") { userMsg.id = ev.user_id; }
        else if (ev.type === "step" && ev.status === "start") {
          sum.innerHTML = `${icon("users")}Atelier · ${esc(ev.role)} (${esc(ev.engine)})…`;
          entity.tokenKick = 1;
          if (ev.final) { entity.split = 0; entity.rippleT = 0; entity.remote = false; }
          else { entity.split = 2; entity.activeCluster = ev.index; entity.remote = /^(?!Local)/.test(ev.engine); }
          if (!ev.final) {
            const c = document.createElement("div"); c.className = "ws-step";
            c.innerHTML = `<div class="ws-h"><b>${esc(ev.role)}</b><span>${esc(ev.engine)}</span></div><div class="md"><span class="live"><span class="mini"></span><span>écrit…</span></span></div>`;
            live.appendChild(c); steps[ev.index] = { el: c, text: "" };
          } else { body.innerHTML = '<span class="live"><span class="mini"></span><span>Rédaction de la réponse finale…</span></span>'; setEmotion("talking"); }
        } else if (ev.type === "step" && ev.status === "token") {
          const s = steps[ev.index]; if (!s) continue; s.text += ev.text;
          if (!q) { q = true; requestAnimationFrame(() => { q = false; steps.forEach((x) => x && (x.el.querySelector(".md").innerHTML = md(x.text))); }); }
        } else if (ev.type === "step" && ev.status === "engine") {
          const s = steps[ev.index]; if (s) { const sp = s.el.querySelector(".ws-h span"); sp.textContent = ev.engine; sp.title = ev.reason || ""; }
          if (ev.reason) toast(`<b>Atelier</b> · relais : ${esc(ev.reason)}`);
        } else if (ev.type === "step" && ev.status === "done") {
          const s = steps[ev.index]; if (s) { s.text = ev.text; setMd(s.el.querySelector(".md"), ev.text); }
        } else if (ev.type === "token") {
          final += ev.text; entity.tokenKick = 1;
          body.innerHTML = md(final); body.lastElementChild?.classList.add("cursor");
          if (atBottom()) scroller.scrollTop = scroller.scrollHeight;
        } else if (ev.type === "done") { asstId = ev.id; final = ev.final; }
        else if (ev.type === "error") throw new Error(ev.message);
      }
    }
    entity.split = 0; entity.remote = false;
    setBusy(false);
    await openConversation(settings.conversationId);
    setEmotion("joy");
  } catch (err) {
    entity.split = 0; entity.remote = false; entity.glitch = 1;
    setBusy(false);
    if (err.name === "AbortError") { toast("Atelier arrêté."); await openConversation(settings.conversationId); }
    else { el.replaceWith(msgEl({ role: "assistant", content: err.message, error: true }, -1)); setEmotion("fear"); }
  } finally {
    controller = null; setBusy(false); scheduleRest(); loadConversations();
  }
}

/* ============================================================
   ESPACES — conversations, consignes et documents par sujet
   ============================================================ */
let spacesList = [], spEditing = null;
const activeSpace = () => spacesList.find((x) => x.id === settings.space) || null;
async function loadSpaces() {
  try { spacesList = (await getJSON("/api/spaces")).spaces; } catch { spacesList = []; }
  if (settings.space && !activeSpace()) { settings.space = null; saveSettings(); }
  renderSpaces();
}
function renderSpaces() {
  const sp = activeSpace();
  $("spaces").hidden = !!sp;
  $("spActive").hidden = !sp;
  if (sp) $("spName").textContent = sp.name;
  $("spList").innerHTML = spacesList.map((x) => `<button data-sp="${x.id}" title="${esc(x.instructions || x.name)}"><span class="ini">${esc((x.name[0] || "?").toUpperCase())}</span><span class="n">${esc(x.name)}</span><span class="c">${x.conversations || ""}</span></button>`).join("");
  $("spList").querySelectorAll("[data-sp]").forEach((b) => { b.onclick = () => enterSpace(+b.dataset.sp); });
  renderConversations(conversations);
}
function enterSpace(id) {
  settings.space = id; saveSettings(); renderSpaces();
  const c = currentConv();
  if (!c || c.space_id !== id) newConversation();
}
$("spBack").onclick = () => { settings.space = null; saveSettings(); renderSpaces(); };
$("spNew").onclick = () => openSpaceDlg(null);
$("spEdit").onclick = () => openSpaceDlg(activeSpace());
function openSpaceDlg(sp) {
  spEditing = sp;
  $("spDlgTitle").textContent = sp ? "Modifier l'espace" : "Nouvel espace";
  $("spDlgName").value = sp?.name || ""; $("spDlgInstr").value = sp?.instructions || "";
  $("spDlgDel").hidden = !sp;
  const cols = (library?.collections || []);
  $("spDlgCols").innerHTML = cols.length ? cols.map((c) => `<label><input type="checkbox" value="${c.id}" ${sp?.collections.includes(c.id) ? "checked" : ""}>${esc(c.name)}${c.kind === "code" ? " · code" : ""}</label>`).join("")
    : '<p class="note">Aucune collection : ajoute des documents dans la Bibliothèque.</p>';
  $("spaceDlg").classList.add("open"); $("spDlgName").focus();
}
$("spDlgCancel").onclick = () => $("spaceDlg").classList.remove("open");
$("spaceDlg").addEventListener("click", (e) => { if (e.target.id === "spaceDlg") $("spaceDlg").classList.remove("open"); });
$("spDlgOk").onclick = async () => {
  const name = $("spDlgName").value.trim();
  if (!name) { $("spDlgName").focus(); return; }
  const body = { name, instructions: $("spDlgInstr").value, collections: [...$("spDlgCols").querySelectorAll("input:checked")].map((i) => +i.value) };
  try {
    const sp = await (await send_(spEditing ? `/api/spaces/${spEditing.id}` : "/api/spaces", spEditing ? "PATCH" : "POST", body)).json();
    $("spaceDlg").classList.remove("open");
    await loadSpaces();
    if (!spEditing) enterSpace(sp.id);
    toast(spEditing ? "Espace mis à jour." : `Espace <b>${esc(sp.name)}</b> créé.`);
  } catch (e) { toast(esc(e.message)); }
};
$("spDlgDel").onclick = async () => {
  if (!spEditing || !confirm(`Supprimer l'espace « ${spEditing.name} » ? Ses conversations sont conservées.`)) return;
  await send_(`/api/spaces/${spEditing.id}`, "DELETE");
  $("spaceDlg").classList.remove("open");
  if (settings.space === spEditing.id) settings.space = null;
  saveSettings(); await loadSpaces(); loadConversations();
};
async function moveToSpace(spaceId) {
  const c = currentConv(); if (!c) { toast("Ouvre d'abord une conversation."); return; }
  await send_(`/api/conversations/${c.id}/space`, "PUT", { space_id: spaceId });
  await loadConversations(); await loadSpaces();
  toast(spaceId ? `Conversation rangée dans <b>${esc(spacesList.find((x) => x.id === spaceId)?.name || "")}</b>.` : "Conversation retirée de l'espace.");
}

/* ============================================================
   RECHERCHE APPROFONDIE et ANALYSE DE DONNÉES — même déroulé :
   étapes en direct, puis réponse finale, enregistrée dans la conversation
   ============================================================ */
let deepNext = false, sbGlobal = null, palCanvases = [];
setInterval(() => getJSON("/api/canvas").then((d) => { palCanvases = d.canvases.slice(0, 12); }).catch(() => {}), 60000);
getJSON("/api/canvas").then((d) => { palCanvases = d.canvases.slice(0, 12); }).catch(() => {});
getJSON("/api/sandbox").then((d) => { sbGlobal = d; }).catch(() => {});
function renderDeepBtn() {
  const b = $("deepBtn"); if (!b) return;
  b.style.display = searchAvailable ? "" : "none";
  b.classList.toggle("on", deepNext);
  b.title = deepNext ? "Recherche approfondie activée pour le prochain message (clic pour annuler)" : "Recherche approfondie : plusieurs recherches, lecture de nombreuses pages, rapport sourcé";
}
$("deepBtn").onclick = () => { deepNext = !deepNext; if (deepNext) { webForce = false; renderWebBtn(); } renderDeepBtn(); input.focus(); if (deepNext) toast("Recherche approfondie : compte 1 à 3 minutes. Atom lit plusieurs sources et rédige un rapport."); };
setInterval(renderDeepBtn, 3000); renderDeepBtn();
function analysisEl(a) {
  const d = document.createElement("div");
  d.innerHTML = (a.images?.length ? `<div class="an-imgs">${a.images.map((f) => `<img src="/api/analysis/${encodeURIComponent(f)}" alt="Graphique" loading="lazy">`).join("")}</div>` : "")
    + `<details class="an-code"><summary>Script Python${a.ok ? "" : " (en échec)"} · ${esc(a.file || "")}</summary><pre><code>${highlightLang(a.code || "", "py")}</code></pre>${a.output ? `<pre>${esc(a.output)}</pre>` : ""}</details>`;
  d.querySelectorAll("img").forEach((im) => { im.onclick = () => window.open(im.src, "_blank"); });
  return d;
}
async function sendSpecial(kind, text, body, fileName) {
  exitHero(); $("empty")?.remove();
  deepNext = false; renderDeepBtn();
  setBusy(true);
  const userMsg = { role: "user", content: text || (fileName ? `Analyse ${fileName}` : ""), meta: fileName ? { attachments: [{ name: fileName, text: "" }] } : undefined };
  history.push(userMsg); chat.appendChild(msgEl(userMsg, history.length - 1));
  setEmotion(kind === "research" ? "curious" : "focus"); setEntityState(kind === "research" ? "recherche approfondie…" : "analyse…");
  const el = document.createElement("div"); el.className = "msg atom";
  el.innerHTML = `<details class="rs-live" open><summary>${kind === "research" ? "Recherche approfondie en cours…" : "Analyse en cours…"}</summary><div class="lv"></div></details><div class="body md"></div>`;
  chat.appendChild(el); scroller.scrollTop = scroller.scrollHeight;
  const lv = el.querySelector(".lv"), out = el.querySelector(".body"), sum = el.querySelector("summary");
  let final = "", q = false;
  controller = new AbortController();
  if (kind === "research") { entity.feeding = true; entity.feedColor = [110, 170, 255]; } else entity.scan = true;
  try {
    const r = await api(`/api/${kind}`, { method: "POST", signal: controller.signal, body: JSON.stringify({ ...body, conversation_id: settings.conversationId }) });
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true }); let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === "meta") { if (settings.conversationId !== ev.conversation_id) { settings.conversationId = ev.conversation_id; saveSettings(); loadConversations(); } }
        else if (ev.type === "progress") { const d = document.createElement("div"); d.className = "st"; d.textContent = ev.text; lv.appendChild(d); sum.textContent = ev.text; entity.tokenKick = 1; scroller.scrollTop = scroller.scrollHeight; }
        else if (ev.type === "token") {
          if (!final) { el.querySelector(".rs-live").open = false; setEmotion("talking"); entity.feeding = false; }
          final += ev.text; entity.tokenKick = 1;
          if (!q) { q = true; requestAnimationFrame(() => { q = false; out.innerHTML = md(final.replace(/^\s*\[[a-z_]+\]\s*/i, "")); scroller.scrollTop = scroller.scrollHeight; }); }
        } else if (ev.type === "error") throw new Error(ev.message);
      }
    }
    setBusy(false);
    await openConversation(settings.conversationId);
    setEmotion("joy");
  } catch (err) {
    setBusy(false); entity.glitch = 1;
    if (err.name === "AbortError") { toast("Arrêté."); await openConversation(settings.conversationId); }
    else { el.replaceWith(msgEl({ role: "assistant", content: err.message, error: true }, -1)); setEmotion("fear"); }
  } finally {
    controller = null; entity.feeding = false; entity.scan = false; setBusy(false); scheduleRest(); loadConversations();
  }
}

/* ============================================================
   CANEVAS — un document modifié à deux, avec ses versions
   ============================================================ */
let cvs = null, cvsTimer = 0, cvsPreview = false;
const CVS_QUICK = [["Corriger", "Corrige l'orthographe, la grammaire et la ponctuation, sans changer le style."], ["Raccourcir", "Raccourcis d'environ un tiers en gardant l'essentiel."],
  ["Développer", "Développe avec plus de détails et d'exemples concrets."], ["Plus formel", "Rends le ton plus formel et professionnel."], ["Plus simple", "Simplifie : phrases courtes, mots simples."],
  ["En anglais", "Traduis en anglais."], ["Structurer", "Structure avec des titres, des listes et des paragraphes courts."]];
$("cvsQuick").innerHTML = CVS_QUICK.map(([t], i) => `<button data-q="${i}">${t}</button>`).join("");
$("cvsQuick").querySelectorAll("button").forEach((b) => { b.onclick = () => canvasAsk(CVS_QUICK[+b.dataset.q][1]); });
function cvsRender() {
  $("canvasPane").classList.toggle("code", cvs.kind === "code");
  $("cvsTitle").value = cvs.title; $("cvsText").value = cvs.content;
  $("cvsVersions").innerHTML = cvs.versions.map((v) => `<option value="${v.i}" ${v.i === cvs.versions.length - 1 ? "selected" : ""}>v${v.i + 1} · ${esc(v.by)} · ${new Date(v.at * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}${v.note ? " · " + esc(v.note.slice(0, 30)) : ""}</option>`).reverse().join("");
  cvsShowView();
}
function cvsShowView() {
  $("cvsText").hidden = cvsPreview; $("cvsView").hidden = !cvsPreview;
  if (cvsPreview) cvs.kind === "code" ? ($("cvsView").innerHTML = `<pre><code>${esc($("cvsText").value)}</code></pre>`) : setMd($("cvsView"), $("cvsText").value);
}
async function openCanvas(id) {
  try { cvs = await getJSON(`/api/canvas/${id}`); } catch (e) { toast(esc(e.message)); return; }
  cvsPreview = false; $("canvasPane").hidden = false; cvsRender(); $("cvsText").focus();
}
async function newCanvas(title, content, kind = "doc") {
  const c = await (await send_("/api/canvas", "POST", { title, content, kind, conversation_id: settings.conversationId })).json();
  openCanvas(c.id);
}
function canvasFromMessage(m) {
  let text = (m.content || "").replace(/^\s*\[[a-z_]+\]\s*/i, "").trim(), kind = "doc";
  const code = text.match(/^```[\w+#.-]*\n([\s\S]*?)\n?```$/);
  if (code) { text = code[1]; kind = "code"; }
  const title = (text.match(/^#+\s*(.+)$/m)?.[1] || currentConv()?.title || "Document").slice(0, 80);
  newCanvas(title, text, kind);
}
function cvsSave() {
  clearTimeout(cvsTimer);
  cvsTimer = setTimeout(async () => {
    if (!cvs) return;
    try { cvs = await (await send_(`/api/canvas/${cvs.id}`, "PUT", { content: $("cvsText").value, title: $("cvsTitle").value })).json(); cvsRenderVersions(); } catch {}
  }, 1200);
}
function cvsRenderVersions() { const keepText = $("cvsText").value; const t = $("cvsTitle").value; cvsRender(); $("cvsText").value = keepText; $("cvsTitle").value = t; }
$("cvsText").addEventListener("input", cvsSave);
$("cvsTitle").addEventListener("input", cvsSave);
const cvsSelection = () => { const t = $("cvsText"); return t.selectionEnd > t.selectionStart ? t.value.slice(t.selectionStart, t.selectionEnd) : ""; };
["select", "keyup", "mouseup"].forEach((ev) => $("cvsText").addEventListener(ev, () => { const s = cvsSelection(); $("cvsSel").textContent = s ? `${s.length} car. sélectionnés` : ""; }));
async function canvasAsk(instruction) {
  instruction = (instruction || $("cvsInstr").value).trim(); if (!cvs || instruction.length < 2) { $("cvsInstr").focus(); return; }
  const selection = cvsSelection();
  clearTimeout(cvsTimer);
  $("canvasPane").classList.add("busy"); $("cvsGo").disabled = true; $("cvsGo").innerHTML = '<span class="spin"></span>'; setEmotion("focus");
  try {
    await send_(`/api/canvas/${cvs.id}`, "PUT", { content: $("cvsText").value, title: $("cvsTitle").value });
    cvs = await (await send_(`/api/canvas/${cvs.id}/edit`, "POST", { instruction, selection })).json();
    cvsRender(); $("cvsInstr").value = ""; entity.absorb = 1; toast(selection ? "Passage modifié par Atom." : "Document modifié par Atom · version précédente dans le menu des versions.");
  } catch (e) { toast(`<b>Canevas</b> · ${esc(e.message)}`); }
  finally { $("canvasPane").classList.remove("busy"); $("cvsGo").disabled = false; $("cvsGo").textContent = "Modifier"; setEmotion("idle"); }
}
$("cvsGo").onclick = () => canvasAsk();
$("cvsInstr").addEventListener("keydown", (e) => { if (e.key === "Enter") canvasAsk(); });
$("cvsVersions").onchange = async (e) => {
  const i = +e.target.value; if (i === cvs.versions.length - 1) return;
  if (!confirm(`Revenir à la version ${i + 1} ? (la version actuelle reste dans l'historique)`)) { cvsRender(); return; }
  const { content } = await getJSON(`/api/canvas/${cvs.id}/versions/${i}`);
  cvs = await (await send_(`/api/canvas/${cvs.id}`, "PUT", { content })).json(); cvsRender();
};
$("cvsPreview").onclick = () => { cvsPreview = !cvsPreview; cvsShowView(); };
$("cvsCopy").onclick = (e) => flashCopy(e.currentTarget, $("cvsText").value);
$("cvsDownload").onclick = () => {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([$("cvsText").value], { type: "text/plain" }));
  a.download = ($("cvsTitle").value || "document").replace(/[^\w\- ]+/g, "").trim() + (cvs?.kind === "code" ? ".txt" : ".md"); a.click();
};
$("cvsClose").onclick = () => { clearTimeout(cvsTimer); if (cvs) send_(`/api/canvas/${cvs.id}`, "PUT", { content: $("cvsText").value, title: $("cvsTitle").value }).catch(() => {}); $("canvasPane").hidden = true; cvs = null; };

/* ============================================================
   SERVEUR PROXMOX — lecture seule
   ============================================================ */
let pxTimer = 0;
const pxGb = (b) => (b / 1e9).toFixed(b > 1e11 ? 0 : 1).replace(".", ",") + " Go";
const pxDur = (s) => { const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600); return d ? `${d} j ${h} h` : `${h} h ${Math.floor((s % 3600) / 60)} min`; };
const pxBar = (pct, warn) => `<div class="bar"><i style="width:${Math.min(100, pct)}%${pct >= warn ? ";background:var(--danger,#e66)" : ""}"></i></div>`;
async function loadProxmox() {
  let d; try { d = await getJSON("/api/proxmox"); } catch (e) { return; }
  $("pxSetup").hidden = d.configured; $("pxBody").hidden = !d.configured;
  clearTimeout(pxTimer);
  if (!d.configured) return;
  const s = d.settings;
  $("pxUpd").textContent = d.ok ? `relevé à ${new Date(d.updated * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
  $("pxAlerts").innerHTML = !d.ok ? `<p class="note" style="color:var(--danger,#e66)">Proxmox injoignable : ${esc(d.error)}</p>`
    : d.alerts.map((a) => `<p class="note" style="color:var(--danger,#e66)">⚠ ${esc(a.title)} — ${esc(a.body)}</p>`).join("");
  $("pxNodes").innerHTML = d.nodes.map((n) => `<div class="px-node"><div class="row" style="justify-content:space-between"><b>${esc(n.name)}</b><span class="note">${n.status === "online" ? `en marche depuis ${pxDur(n.uptime)}` : esc(n.status)}</span></div>
    ${n.model ? `<p class="note" style="margin:2px 0 6px">${esc(n.model)} · ${n.cores} cœurs${n.load ? ` · charge ${n.load.map(esc).join(" / ")}` : ""}</p>` : ""}
    <div class="metric"><div class="l"><span>Processeur</span><span>${n.cpu.toFixed(0)} %</span></div>${pxBar(n.cpu, s.cpu)}</div>
    <div class="metric"><div class="l"><span>Mémoire</span><span>${pxGb(n.mem_used)} / ${pxGb(n.mem_total)}</span></div>${pxBar(n.mem, s.mem)}</div>
    <div class="metric"><div class="l"><span>Disque système</span><span>${n.disk.toFixed(0)} %</span></div>${pxBar(n.disk, s.storage)}</div></div>`).join("");
  $("pxGuests").innerHTML = d.guests.map((g) => `<div class="px-g ${g.status === "running" ? "" : "off"}"><span class="st-dot ${g.status === "running" ? "ok" : "off"}"></span>
    <span class="n"><b>${esc(g.name)}</b> <small>${g.type} ${g.id}${d.nodes.length > 1 ? " · " + esc(g.node) : ""}</small></span>
    ${g.status === "running" ? `<span class="v">${g.cpu.toFixed(0)} %</span><span class="v">${pxGb(g.mem_used)}</span><span class="v t">${pxDur(g.uptime)}</span>` : `<span class="v t">${esc(g.status)}</span>`}</div>`).join("") || '<p class="note">Aucune VM ni conteneur.</p>';
  $("pxStorages").innerHTML = d.storages.map((st) => `<div class="metric"><div class="l"><span>${esc(st.name)} <small class="note">${esc(st.node)} · ${esc(st.kind || "")}</small></span><span>${pxGb(st.used)} / ${pxGb(st.total)}</span></div>${pxBar(st.pct, s.storage)}</div>`).join("");
  $("pxNotify").checked = s.notify; $("pxGuestDown").checked = s.guest_down;
  $("pxCpu").value = s.cpu; $("pxMem").value = s.mem; $("pxMin").value = s.minutes; $("pxSto").value = s.storage;
  if ($("settings").classList.contains("open")) pxTimer = setTimeout(loadProxmox, 30000);
}
const pxSave = (patch) => send_("/api/proxmox", "PUT", patch).then(() => toast("Réglages d'alerte enregistrés.")).catch((e) => toast(esc(e.message)));
$("pxRefresh").onclick = loadProxmox;
$("pxNotify").onchange = () => pxSave({ notify: $("pxNotify").checked });
$("pxGuestDown").onchange = () => pxSave({ guest_down: $("pxGuestDown").checked });
[["pxCpu", "cpu"], ["pxMem", "mem"], ["pxMin", "minutes"], ["pxSto", "storage"]].forEach(([id, k]) => { $(id).onchange = () => pxSave({ [k]: +$(id).value }); });

/* ============================================================
   THÈME
   ============================================================ */
const darkMQ = matchMedia("(prefers-color-scheme: dark)");
function applyTheme() {
  const t = settings.theme || "dark";
  const eff = t === "auto" ? (darkMQ.matches ? "dark" : "light") : t;
  document.documentElement.dataset.theme = eff;
  document.querySelector('meta[name="theme-color"]').content = eff === "light" ? "#f6f6f3" : "#1b1b1b";
}
darkMQ.addEventListener?.("change", applyTheme);
choiceRow("themeRow", "theme", [["dark", "Sombre"], ["light", "Clair"], ["auto", "Automatique"]]);
const _applyLook = applyLook;
applyLook = function () { _applyLook(); applyTheme(); };
document.body.classList.toggle("no-hero", settings.heroWelcome === false);
$("heroToggle").checked = settings.heroWelcome !== false;
$("heroToggle").onchange = () => { settings.heroWelcome = $("heroToggle").checked; saveSettings(); document.body.classList.toggle("no-hero", !settings.heroWelcome); if (!settings.heroWelcome) exitHero(); else if (!history.length) enterHero(); };

/* ============================================================
   PALETTE DE COMMANDES (Ctrl+K)
   ============================================================ */
let palItems = [], palSel = 0, palTimer = 0;
function palActions() {
  const A = (g, ic, label, run, hint = "") => ({ g, ic, label, run, hint });
  const list = [
    A("Actions", "plus", "Nouvelle conversation", () => newConversation(), "Ctrl ⇧ O"),
    A("Actions", "orb", "Mode présence", () => enterPresence()),
    A("Canevas", "doc", "Nouveau canevas (document vide)", () => newCanvas("Nouveau document", "")),
    ...(palCanvases || []).map((c) => A("Canevas", "doc", `Ouvrir le canevas « ${c.title} »`, () => openCanvas(c.id))),
    A("Espaces", "folder", "Nouvel espace…", () => openSpaceDlg(null)),
    ...spacesList.map((x) => A("Espaces", "folder", `Ouvrir l'espace « ${x.name} »`, () => enterSpace(x.id))),
    ...(currentConv() ? spacesList.map((x) => A("Espaces", "folder", `Ranger cette conversation dans « ${x.name} »`, () => moveToSpace(x.id))) : []),
    ...(currentConv()?.space_id ? [A("Espaces", "folder", "Retirer cette conversation de son espace", () => moveToSpace(null))] : []),
    A("Actions", "globe", webForce ? "Ne plus forcer la recherche web" : "Rechercher sur Internet pour le prochain message", () => { webForce = !webForce; renderWebBtn(); }),
    A("Actions", "download", "Exporter la conversation en Markdown", () => $("exportBtn").click()),
    A("Aller à", "list", "Discussion", () => showView("chat")),
    A("Aller à", "library", "Bibliothèque", () => showView("library")),
    A("Aller à", "code", "Code", () => showView("code")),
    A("Apparence", "panel", (document.documentElement.dataset.theme === "light" ? "Thème sombre" : "Thème clair"), () => { settings.theme = document.documentElement.dataset.theme === "light" ? "dark" : "light"; saveSettings(); applyTheme(); choiceRow("themeRow", "theme", [["dark", "Sombre"], ["light", "Clair"], ["auto", "Automatique"]]); }),
    A("Apparence", "sidebar", "Afficher / masquer la barre latérale", () => $("sideClose").click()),
    A("Apparence", "panel", "Afficher / masquer le panneau de l'entité", () => $("panelBtn").click()),
  ];
  if (hybridState?.configured) for (const [v, t] of [["local", "Local"], ["auto", "Auto"], ["mistral", hybridState.name]]) list.push(A("Moteur", v === "local" ? "orb" : "spark", `Répondre avec : ${t}`, () => setEngine(v)));
  if (workshopCfg?.enabled) list.push(A("Actions", "users", "Atelier multi-IA pour le prochain message", () => { workshopNext = true; $("wsBtn").classList.add("on"); }));
  for (const o of [...modelSel.options]) if (o.value) list.push(A("Modèle", "spark", `Modèle : ${o.value}`, () => { modelSel.value = o.value; modelSel.onchange(); }));
  for (const t of document.querySelectorAll(".tabs .tab")) list.push(A("Réglages", "settings", `Réglages · ${t.textContent.trim()}`, () => openSettings(t.dataset.tab)));
  list.push(A("Compte", "lock", "Me déconnecter", () => $("secLogout").click()));
  return list;
}
function fuzzy(q, text) {
  if (!q) return { score: 1, html: esc(text) };
  const t = text.toLowerCase(), ql = q.toLowerCase();
  const at = t.indexOf(ql);
  if (at >= 0) return { score: 100 - at, html: esc(text.slice(0, at)) + `<mark>${esc(text.slice(at, at + q.length))}</mark>` + esc(text.slice(at + q.length)) };
  let j = 0, out = "", score = 0;
  for (let i = 0; i < text.length; i++) {
    if (j < ql.length && t[i] === ql[j]) { out += `<mark>${esc(text[i])}</mark>`; j++; score += 2; } else out += esc(text[i]);
  }
  return j === ql.length ? { score, html: out } : null;
}
async function palRender() {
  const q = $("palIn").value.trim();
  const items = [];
  for (const c of conversations.slice(0, 200)) {
    const m = fuzzy(q, c.title); if (m) items.push({ g: "Conversations", ic: c.pinned ? "pin" : "list", html: m.html, score: m.score + (q ? 5 : 0), hint: groupOf(c.updated_at), run: () => openConversation(c.id) });
  }
  if (currentView === "code" && q.length >= 2) for (const f of code.files) { const m = fuzzy(q, f.path); if (m) items.push({ g: "Fichiers du projet", ic: "doc", html: m.html, score: m.score, run: () => openFile(f.path) }); }
  for (const c of library.collections || []) { const m = fuzzy(q, c.name); if (m && q) items.push({ g: "Bibliothèque", ic: c.kind === "code" ? "code" : "folder", html: m.html, score: m.score, run: () => { showView(c.kind === "code" ? "code" : "library"); if (c.kind === "code") { code.project = c.id; loadCodeProjects(); } else { libSel = c.id; renderLibrary(); } } }); }
  for (const a of palActions()) { const m = fuzzy(q, a.label); if (m) items.push({ g: a.g, ic: a.ic, html: m.html, score: m.score, hint: a.hint, run: a.run }); }
  const order = ["Conversations", "Actions", "Aller à", "Fichiers du projet", "Bibliothèque", "Moteur", "Modèle", "Apparence", "Réglages", "Compte"];
  items.sort((a, b) => q ? b.score - a.score : order.indexOf(a.g) - order.indexOf(b.g));
  const top = q ? items.slice(0, 40) : [...items.filter((x) => x.g === "Conversations").slice(0, 5), ...items.filter((x) => x.g !== "Conversations").slice(0, 14)];
  // recherche dans le contenu des conversations
  if (q.length >= 3) {
    clearTimeout(palTimer);
    palTimer = setTimeout(async () => {
      try {
        const r = (await getJSON("/api/search?q=" + encodeURIComponent(q))).results.filter((c) => !top.some((x) => x.g === "Conversations" && x.html.replace(/<[^>]+>/g, "") === c.title));
        if (!r.length || $("palIn").value.trim() !== q) return;
        palItems = [...palItems, ...r.slice(0, 8).map((c) => ({ g: "Dans les messages", ic: "search", html: esc(c.title) + (c.snippet ? ` <small style="margin-left:6px;color:var(--faint);font-family:var(--sans)">${esc(c.snippet.slice(0, 60))}</small>` : ""), run: () => openConversation(c.id) }))];
        palDraw();
      } catch {}
    }, 220);
  }
  palItems = top; palSel = 0; palDraw();
}
function palDraw() {
  const box = $("palList");
  box.innerHTML = "";
  let g = null;
  palItems.forEach((it, k) => {
    if (it.g !== g) { g = it.g; box.insertAdjacentHTML("beforeend", `<div class="pal-g">${esc(g)}</div>`); }
    const b = document.createElement("button");
    b.className = "pal-i" + (k === palSel ? " sel" : "");
    b.innerHTML = `${icon(it.ic)}<span>${it.html}</span>${it.hint ? `<small>${esc(it.hint)}</small>` : ""}`;
    b.onmouseenter = () => { palSel = k; box.querySelectorAll(".pal-i").forEach((x, n) => x.classList.toggle("sel", n === k)); };
    b.onclick = () => palRun(k);
    box.appendChild(b);
  });
  if (!palItems.length) box.innerHTML = '<div class="side-empty">Aucun résultat.</div>';
}
function palRun(k) { const it = palItems[k]; closePalette(); it?.run(); }
function openPalette() { $("palette").classList.add("open"); $("palIn").value = ""; palRender(); setTimeout(() => $("palIn").focus(), 20); }
function closePalette() { $("palette").classList.remove("open"); }
$("palIn").addEventListener("input", palRender);
$("palIn").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    palSel = (palSel + (e.key === "ArrowDown" ? 1 : -1) + palItems.length) % Math.max(1, palItems.length);
    $("palList").querySelectorAll(".pal-i").forEach((x, n) => { x.classList.toggle("sel", n === palSel); if (n === palSel) x.scrollIntoView({ block: "nearest" }); });
  } else if (e.key === "Enter") { e.preventDefault(); palRun(palSel); }
  else if (e.key === "Escape") { e.preventDefault(); closePalette(); }
});
$("palette").addEventListener("click", (e) => { if (e.target.id === "palette") closePalette(); });

/* ============================================================
   MOBILE : barre d'onglets et gestes
   ============================================================ */
function syncTabbar() {
  const on = app.classList.contains("panel-open") ? "atom" : app.classList.contains("side-open") ? "chats" : currentView === "chat" ? "chats" : currentView;
  document.querySelectorAll("#tabbar button").forEach((b) => b.classList.toggle("on", b.dataset.tab === on));
}
document.querySelectorAll("#tabbar button").forEach((b) => b.onclick = () => {
  const t = b.dataset.tab;
  app.classList.remove("panel-open");
  if (t === "chats") { if (currentView !== "chat") { showView("chat"); app.classList.remove("side-open"); } else app.classList.toggle("side-open"); }
  else if (t === "library" || t === "code") { app.classList.remove("side-open"); showView(t); }
  else if (t === "atom") { app.classList.remove("side-open"); app.classList.add("panel-open"); refreshPanel(); refreshSystem(); }
  else if (t === "settings") { app.classList.remove("side-open"); openSettings(); }
  applyLayout(); syncTabbar();
});
new MutationObserver(syncTabbar).observe(app, { attributes: true, attributeFilter: ["class"] });
syncTabbar();
(() => {
  let sx = 0, sy = 0, edge = null, t0 = 0;
  addEventListener("touchstart", (e) => {
    if (!narrow() || e.touches.length !== 1) return;
    const x = e.touches[0].clientX; sx = x; sy = e.touches[0].clientY; t0 = Date.now();
    edge = app.classList.contains("side-open") ? "closeSide" : app.classList.contains("panel-open") ? "closePanel"
      : x < 28 ? "left" : x > innerWidth - 28 ? "right" : null;
  }, { passive: true });
  addEventListener("touchend", (e) => {
    if (!edge) return;
    const t = e.changedTouches[0], dx = t.clientX - sx, dy = t.clientY - sy;
    if (Math.abs(dy) > Math.abs(dx) || Date.now() - t0 > 700) { edge = null; return; }
    if (edge === "left" && dx > 60) app.classList.add("side-open");
    else if (edge === "right" && dx < -60) { app.classList.add("panel-open"); refreshPanel(); }
    else if (edge === "closeSide" && dx < -60) app.classList.remove("side-open");
    else if (edge === "closePanel" && dx > 60) app.classList.remove("panel-open");
    edge = null; applyLayout();
  }, { passive: true });
})();

/* ============================================================
   GLISSER-DÉPOSER : message, bibliothèque, ou directement dans l'entité
   ============================================================ */
function dropContext() {
  if (currentView === "library") {
    const c = library.collections.find((x) => x.id === libSel && x.kind === "docs") || library.collections.find((x) => x.kind === "docs");
    return ["Ajouter à la bibliothèque", c ? `Collection « ${c.name} » · Atom lira et indexera tes documents` : "Bibliothèque"];
  }
  if (currentView === "code") return ["Les projets s'ajoutent depuis GitHub ou un dossier", "Utilise « Ajouter un projet » : un dépôt n'est pas un simple fichier"];
  return ["Joindre au message", "Ou dépose-les sur l'entité pour les ranger dans ta bibliothèque"];
}
addEventListener("dragenter", (e) => {
  if (![...(e.dataTransfer?.types || [])].includes("Files")) return;
  const [t, s2] = dropContext(); $("dropTitle").textContent = t; $("dropSub").textContent = s2;
  entity.feedColor = [235, 235, 240]; entity.hover = true; entity.typingAt = performance.now();
});
stageEl.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); stageEl.classList.add("dropover"); entity.feeding = true; });
stageEl.addEventListener("dragleave", () => { stageEl.classList.remove("dropover"); entity.feeding = false; });
stageEl.addEventListener("drop", async (e) => {
  e.preventDefault(); e.stopPropagation();
  stageEl.classList.remove("dropover"); $("drop").classList.remove("on"); dragDepth = 0;
  const files = [...(e.dataTransfer?.files || [])];
  if (!files.length) return;
  if (!library.collections.length) { try { library = await getJSON("/api/library"); } catch {} }
  const c = library.collections.find((x) => x.kind === "docs");
  if (c) { entity.absorb = 1; uploadDocs(c.id, files); } else toast("Aucune collection de documents.");
});
addEventListener("dragleave", () => { if (!dragDepth) { entity.hover = false; } });

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
loadLibrary();
loadSpaces();
if (store.get("view", "chat") === "code" || store.get("view", "chat") === "library") showView(store.get("view", "chat"));
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
