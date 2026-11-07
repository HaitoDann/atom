# Bibliothèques embarquées

Servies par Atom lui-même (pas de CDN) : fonctionnent hors ligne et permettent une CSP `script-src 'self'`.
Chargées à la demande, seulement quand une réponse contient une formule ou un schéma.

| Bibliothèque | Version | Source | Fichiers |
|---|---|---|---|
| KaTeX | 0.16.9 | npm `katex@0.16.9` (`dist/`) | `katex.min.js`, `katex.min.css`, polices `.woff2` |
| Mermaid | 10.9.1 | npm `mermaid@10.9.1` (`dist/`) | `mermaid.min.js` |

Mise à jour : `npm pack katex@X mermaid@Y`, recopier les mêmes fichiers, changer la version ici.
