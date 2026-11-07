// Accessibilité (axe-core, règles WCAG 2.1 A et AA) et parcours sur écran de téléphone.
const { test, expect, devices } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

const PASSWORD = "motdepasse-e2e";

async function login(page) {
  await page.goto("/");
  await expect(page.locator("#login")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.fill("#loginPw", PASSWORD);
  const status = await (await page.request.get("/api/auth/status")).json();
  if (status.setup_needed) { await expect(page.locator("#loginPw2")).toBeVisible(); await page.fill("#loginPw2", PASSWORD); }
  await page.click("#loginBtn");
  await expect(page.locator("#login")).toBeHidden();
  await page.waitForLoadState("networkidle");
}

/** Violations graves ou critiques, sous une forme lisible dans le rapport. */
async function audit(page, include) {
  let b = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]);
  if (include) b = b.include(include);
  const r = await b.analyze();
  return r.violations.filter((v) => ["serious", "critical"].includes(v.impact))
    .map((v) => `${v.id} (${v.impact}) : ${v.help} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`);
}

test.describe.configure({ mode: "serial" });

test("accessibilité : écran de connexion", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#login")).toBeVisible();
  expect(await audit(page, "#login")).toEqual([]);
});

test("accessibilité : discussion", async ({ page }) => {
  await login(page);
  expect(await audit(page)).toEqual([]);
});

test("accessibilité : réglages (consommation, sauvegarde)", async ({ page }) => {
  await login(page);
  await page.evaluate(() => openSettings("usage"));
  await expect(page.locator("#usLive")).toHaveClass(/on/, { timeout: 10_000 });
  expect(await audit(page, "#settings")).toEqual([]);
  await page.evaluate(() => openSettings("backup"));
  expect(await audit(page, "#settings")).toEqual([]);
});

test.describe("téléphone", () => {
  // Taille, densité et écran tactile d'un iPhone 13, avec Chromium (seul navigateur installé).
  const { defaultBrowserType, ...phone } = devices["iPhone 13"];   // eslint-disable-line no-unused-vars
  test.use(phone);

  test("discussion sur téléphone : pas de défilement horizontal, barre d'onglets, envoi", async ({ page }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await login(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await expect(page.locator("#tabbar, .tabbar").first()).toBeVisible();
    await expect(async () => {
      await page.fill("#input", "Bonjour depuis mon téléphone");
      await expect(page.locator("#send")).toBeEnabled({ timeout: 1000 });
    }).toPass({ timeout: 10_000 });
    await page.click("#send");
    await expect(page.locator(".msg.atom").last()).toContainText("téléphone", { timeout: 15_000 });
    const box = await page.locator(".msg.atom").last().boundingBox();
    expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize().width + 1);   // la réponse tient dans l'écran
    expect(errors).toEqual([]);
  });

  test("réglages sur téléphone : consommation lisible", async ({ page }) => {
    await login(page);
    await page.evaluate(() => openSettings("usage"));
    await expect(page.locator(".us-tile").first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(await audit(page, "#settings")).toEqual([]);
  });
});

test("accessibilité : lanceur d'atelier", async ({ page }) => {
  await login(page);
  await page.click("#navWs");
  await expect(page.locator("#wlGo")).toBeVisible();
  await page.fill("#wlText", "Compare deux options pour mon serveur");
  await expect(page.locator("#wlFlow .ws-node").first()).toBeVisible();
  expect(await audit(page, "#wsLaunch")).toEqual([]);
});
