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
