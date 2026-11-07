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
  await page.fill("#loginPw", PASSWORD);
  if (await page.locator("#loginPw2").isVisible()) await page.fill("#loginPw2", PASSWORD);   // premier lancement
  await page.click("#loginBtn");
  await expect(page.locator("#login")).toBeHidden();
}

test.describe.configure({ mode: "serial" });

test("connexion puis discussion en streaming", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.fill("#input", "Bonjour Atom");
  await page.click("#send");
  await expect(page.locator(".msg.user").last()).toContainText("Bonjour Atom");
  await expect(page.locator(".msg.atom").last()).toContainText("Tu m'as dit : « Bonjour Atom »", { timeout: 15_000 });
  expect(errors).toEqual([]);
});

test("la conversation survit au rechargement", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.fill("#input", "Message à retrouver");
  await page.click("#send");
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
  await page.fill("#loginPw", "pas-le-bon");
  await page.click("#loginBtn");
  await expect(page.locator("#loginErr")).not.toBeEmpty();
  await expect(page.locator("#login")).toBeVisible();
});
