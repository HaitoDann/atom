// Lance Atom en mode test (ATOM_PROVIDER=mock : pas de modèle, pas d'Internet) sur une base jetable,
// puis pilote l'interface dans Chromium.
const { defineConfig } = require("@playwright/test");
const os = require("os");
const path = require("path");
const fs = require("fs");

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "atom-e2e-"));
const PORT = process.env.ATOM_E2E_PORT || "8799";

module.exports = defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  workers: 1,                 // une seule base, un seul mot de passe : les tests partagent le serveur
  fullyParallel: false,
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    ...(process.env.ATOM_CHROMIUM ? { launchOptions: { executablePath: process.env.ATOM_CHROMIUM } } : {}),
  },
  webServer: {
    command: `python -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT}`,
    cwd: path.join(__dirname, "..", "api"),
    url: `http://127.0.0.1:${PORT}/api/auth/status`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      ATOM_PROVIDER: "mock",
      ATOM_DB: path.join(tmp, "atom.db"),
      ATOM_BACKUP_DIR: path.join(tmp, "backups"),
      ATOM_PROJECTS_DIR: path.join(tmp, "projects"),
      ATOM_WEB: path.join(__dirname, "..", "web"),
      ATOM_SEARXNG_URL: "",
      ATOM_NTFY_URL: "",
      ATOM_TELEGRAM_TOKEN: "",
      ATOM_PASSWORD: "",
      // NAS simulé par un dossier local : copie chiffrée, vérification et restauration testées de bout en bout
      ATOM_OFFSITE_DIR: (fs.mkdirSync(path.join(tmp, "nas"), { recursive: true }), path.join(tmp, "nas")),
      ATOM_OFFSITE_KEY: "phrase-e2e-pour-le-nas",
      ATOM_OFFSITE_NAME: "NAS-VinX",
      PATH: process.env.PATH,
    },
  },
});
