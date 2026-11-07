"use strict";

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
