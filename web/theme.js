// Thème appliqué avant l'affichage, pour éviter un flash (fichier séparé : la CSP interdit les scripts en ligne).
try {
  const t = (JSON.parse(localStorage.getItem("atom.settings") || "{}").theme) || "dark";
  document.documentElement.dataset.theme = t === "auto" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : t;
} catch {}
