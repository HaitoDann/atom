"use strict";

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
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const waveA = new Float32Array(N), wavePaths = Array.from({ length: 7 }, () => null);   // onde de couleur (repos)

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
    // Au repos : respiration calme (environ 7 par minute) — inspiration douce, petite pause, expiration —
    // et une onde de couleur subtile qui parcourt la maille. Les autres états gardent leur rythme propre.
    const restful = entity.activity === "idle" && !typing && !(entity.workK > 0.05);
    entity.idleK = (entity.idleK || 0) + ((restful ? 1 : 0) - (entity.idleK || 0)) * Math.min(1, dt * 0.8);
    const idleK = entity.idleK, calm = reducedMotion.matches;
    const cyc = (t % 8.6) / 8.6;                                                    // un cycle ≈ 8,6 s
    const inhale = cyc < 0.42 ? 0.5 - 0.5 * Math.cos(Math.PI * cyc / 0.42)         // inspiration
      : cyc < 0.5 ? 1                                                               // courte pause, poumons pleins
      : 0.5 + 0.5 * Math.cos(Math.PI * (cyc - 0.5) / 0.5);                          // expiration plus longue
    const breathR = (1 - idleK) * Math.sin(t * breath) * 0.016 + idleK * (inhale - 0.4) * (calm ? 0.012 : 0.045);
    const breathL = 1 + idleK * (inhale - 0.5) * 0.28;                              // la maille s'éclaire en inspirant
    const rad = cur.radius * (1 + breathR) * (1 - entity.blink * 0.06) * (1 - entity.absorb * 0.1) * (1 + entity.grow * 0.25);
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
        let al = 0.5 * cur.dim * globalA * breathL * Math.min(depthA(szA[a]), depthA(szA[b]));
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
      for (const i of nodeIdx) drawNode(i, 0.95 * breathL);
      for (const i of orbNodes) drawNode(i, 0.6);

      // ---- au repos : onde de couleur qui traverse la maille en diagonale (lente, discrète, teinte qui dérive)
      if (idleK > 0.02) {
        const period = calm ? 16 : 9.5, u = (t % period) / period, pos = -1.6 + 3.2 * u, sig = 0.3;
        const hue = 215 + 45 * Math.sin(t * 0.045) + 20 * Math.sin(t * 0.017);       // bleu glacier ↔ lavande ↔ rose pâle
        for (const i of nodeIdx) {
          const d = (ay[i] * 0.78 - ax[i] * 0.62) / (R0 || 1) - pos;
          waveA[i] = Math.exp(-(d * d) / (2 * sig * sig));
        }
        for (let b2 = 0; b2 < 7; b2++) wavePaths[b2] = null;
        for (let e = 0; e < edges.length; e++) {
          const a = edges[e][0], b = edges[e][1];
          if (!visA[a] || !visA[b]) continue;
          const w = (waveA[a] + waveA[b]) * 0.5 * Math.min(depthA(szA[a]), depthA(szA[b]));
          const k = Math.min(6, (w * 7) | 0);
          if (k <= 0) continue;
          (wavePaths[k] ||= new Path2D());
          wavePaths[k].moveTo(sxA[a], syA[a]); wavePaths[k].lineTo(sxA[b], syA[b]);
        }
        ctx.strokeStyle = `hsl(${hue.toFixed(0)},60%,${lightT ? 45 : 74}%)`; ctx.lineWidth = lw * 1.15;
        for (let k = 1; k <= 6; k++) if (wavePaths[k]) { ctx.globalAlpha = (k / 6) * 0.3 * idleK * globalA * cur.dim; ctx.stroke(wavePaths[k]); }
        ctx.fillStyle = `hsl(${(hue + 15).toFixed(0)},65%,${lightT ? 48 : 80}%)`;
        for (const i of nodeIdx) {
          const w = waveA[i];
          if (w < 0.3 || !visA[i]) continue;
          const f = szA[i] > 0 ? 1 - Math.min(0.8, szA[i] / 260) : 1;
          ctx.globalAlpha = Math.min(1, w * f * 0.32 * idleK * globalA);
          ctx.beginPath(); ctx.arc(sxA[i], syA[i], (1 + 1.3 * f) * pxSize * (1 + P * 0.3), 0, 6.283); ctx.fill();
        }
      }
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
