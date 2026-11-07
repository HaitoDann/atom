// Parcours essentiels de l'interface, avec le modèle simulé du backend.
const { test, expect } = require("@playwright/test");

const PASSWORD = "motdepasse-e2e";

/** Erreurs JavaScript de la page (hors 401 attendus avant connexion). */
function watchErrors(page) {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error" && !/status of 401/.test(m.text())) errors.push(m.text());
  });
  return errors;
}

async function login(page) {
  await page.goto("/");
  await expect(page.locator("#login")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.fill("#loginPw", PASSWORD);
  // Premier lancement : le champ de confirmation apparaît une fois l'état demandé au serveur.
  const status = await (await page.request.get("/api/auth/status")).json();
  if (status.setup_needed) {
    await expect(page.locator("#loginPw2")).toBeVisible();
    await page.fill("#loginPw2", PASSWORD);
  }
  await page.click("#loginBtn");
  await expect(page.locator("#login")).toBeHidden();
  await page.waitForLoadState("networkidle");   // conversations et brouillon restaurés
}

/** Saisit puis envoie ; recommence si l'interface a vidé le champ entre-temps (restauration du brouillon). */
async function send(page, text) {
  await expect(async () => {
    await page.fill("#input", text);
    await expect(page.locator("#send")).toBeEnabled({ timeout: 1000 });
  }).toPass({ timeout: 10_000 });
  await page.click("#send");
}

test.describe.configure({ mode: "serial" });

test("connexion puis discussion en streaming", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await send(page, "Bonjour Atom");
  await expect(page.locator(".msg.user").last()).toContainText("Bonjour Atom");
  await expect(page.locator(".msg.atom").last()).toContainText("Tu m'as dit : « Bonjour Atom »", { timeout: 15_000 });
  expect(errors).toEqual([]);
});

test("la conversation survit au rechargement", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await send(page, "Message à retrouver");
  await expect(page.locator(".msg.atom").last()).toContainText("Message à retrouver", { timeout: 15_000 });
  await page.reload();
  await expect(page.locator(".msg.user").filter({ hasText: "Message à retrouver" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("palette de commandes (Ctrl+K)", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.keyboard.press("Control+k");
  const palette = page.locator("#palette");
  await expect(palette).toHaveClass(/open/);
  await expect(page.locator("#palIn")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(palette).not.toHaveClass(/open/);
  expect(errors).toEqual([]);
});

test("mauvais mot de passe refusé", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#login")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.fill("#loginPw", "pas-le-bon");
  await page.click("#loginBtn");
  await expect(page.locator("#loginErr")).not.toBeEmpty();
  await expect(page.locator("#login")).toBeVisible();
});

test("en-têtes de sécurité : CSP stricte", async ({ page }) => {
  const r = await page.request.get("/");
  const csp = r.headers()["content-security-policy"] || "";
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("object-src 'none'");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).not.toMatch(/script-src[^;]*'unsafe-(inline|eval)'/);
  expect(r.headers()["x-frame-options"]).toBe("DENY");
  expect(csp).not.toContain("googleapis");
});

test("polices embarquées chargées (aucune ressource externe)", async ({ page }) => {
  const external = [];
  page.on("request", (req) => { if (!req.url().startsWith("http://127.0.0.1")) external.push(req.url()); });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  expect(await page.evaluate(async () => { await document.fonts.ready; return document.fonts.check("14px Geist"); })).toBe(true);
  expect(external).toEqual([]);
});

test("du HTML dans une réponse n'est jamais exécuté", async ({ page }) => {
  const errors = watchErrors(page);
  let dialog = false;
  page.on("dialog", (d) => { dialog = true; d.dismiss(); });
  await login(page);
  await send(page, `Test <img src=x onerror="alert(1)"> [lien](javascript:alert(1)) <script>alert(2)</script>`);
  const last = page.locator(".msg.atom").last();
  await expect(last).toContainText("onerror", { timeout: 15_000 });   // affiché comme du texte
  await expect(page.locator(".msg img[src='x']")).toHaveCount(0);
  await expect(page.locator(".msg script")).toHaveCount(0);
  await expect(page.locator('.msg a[href^="javascript"]')).toHaveCount(0);
  expect(dialog).toBe(false);
  expect(errors).toEqual([]);
});

test("formules et schémas rendus sans violation de la CSP", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await send(page, "Formule\n\n$$x^2 + y^2 = z^2$$\n\n```mermaid\ngraph TD\n  A --> B\n```");
  const last = page.locator(".msg.atom").last();
  await expect(last.locator(".katex")).toBeVisible({ timeout: 20_000 });
  await expect(last.locator(".mm svg")).toBeVisible({ timeout: 20_000 });
  expect(errors.filter((e) => /Content Security Policy|Refused to/i.test(e))).toEqual([]);
  expect(errors).toEqual([]);
});

test("consommation : les appels apparaissent en direct", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.evaluate(() => openSettings("usage"));
  await expect(page.locator("#usLive")).toHaveClass(/on/, { timeout: 10_000 });
  const before = await page.locator("#usFeed li:not(.none)").count();
  await page.evaluate(() => closeSettings());
  await send(page, "Combien de tokens ?");
  await expect(page.locator(".msg.atom").last()).toContainText("Combien de tokens", { timeout: 15_000 });
  await page.evaluate(() => openSettings("usage"));
  await expect(page.locator("#usFeed li:not(.none)")).toHaveCount(before + 1, { timeout: 10_000 });
  await expect(page.locator("#usFeed li").first()).toContainText("Local");
  await expect(page.locator("#usProv")).toContainText("Local (Ollama)");
  await expect(page.locator(".us-tile").first()).toContainText("Appels");
  await expect(page.locator("#alInfo")).toContainText("quota atteint");
  // Un appel pendant que la rubrique est ouverte : il doit arriver par le flux, sans rechargement.
  const n = await page.locator("#usFeed li:not(.none)").count();
  await page.evaluate(async () => {
    const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json", "X-Atom": "1" },
      body: JSON.stringify({ message: "En direct", auto_memory: false, web: "off", scope: "none" }) });
    await r.text();
  });
  await expect(page.locator("#usFeed li:not(.none)")).toHaveCount(n + 1, { timeout: 10_000 });
  await expect(page.locator("#usFeed li.fresh")).toHaveCount(1);
  await page.fill("#usTry", "Corrige ce bug dans ma fonction python");
  await page.click("#usTryGo");
  await expect(page.locator("#usTryOut")).toContainText("Code");
  expect(errors).toEqual([]);
});

test("mode Code et bibliothèque s'ouvrent sans erreur", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.evaluate(() => showView("code"));
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => showView("library"));
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => showView("chat"));
  expect(errors).toEqual([]);
});

test("sauvegarde : copie chiffrée sur le NAS, puis test de restauration", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.evaluate(() => openSettings("backup"));
  await expect(page.locator("#nasTitle")).toHaveText("Copie sur NAS-VinX");
  await expect(page.locator("#nasState")).toContainText("joignable");
  await page.click("#nasPush");
  await expect(page.locator("#nasList li:not(.none)")).toHaveCount(1, { timeout: 15_000 });
  await expect(page.locator("#nasList")).toContainText(".db.enc");
  await page.click("#nasVerify");
  await expect(page.locator("#nasState")).toContainText("réussi", { timeout: 15_000 });
  expect(errors).toEqual([]);
});

test("tableau de bord : Grafana affiché dans l'interface, à travers Atom", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.click("#navDash");
  await expect(page.locator("#title")).toHaveText("Tableau de bord");
  const frame = page.frameLocator("#dashFrame");
  await expect(frame.locator("#g")).toHaveText("Grafana factice", { timeout: 10_000 });
  await expect(frame.locator("#path")).toContainText("/grafana/d/atom/atom");
  await expect(frame.locator("#path")).toContainText("kiosk");
  await expect(frame.locator("#cookie")).toHaveText("aucun cookie");          // la session d'Atom ne part pas chez Grafana
  await page.click("#dashCheck");
  await expect(page.locator("#dashReport")).toContainText("panneaux répondent sans erreur", { timeout: 10_000 });
  await page.click('#dashRange button[data-r="now-7d"]');
  await expect(frame.locator("#path")).toContainText("from=now-7d");
  await page.click("#navDash");                                              // retour à la discussion
  await expect(page.locator("#dashView")).toBeHidden();
  expect(errors).toEqual([]);
});
