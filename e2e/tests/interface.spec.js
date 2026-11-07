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
