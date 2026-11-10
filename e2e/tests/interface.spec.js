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
  // Saisie et clic ensemble : si l'interface vide le champ entre les deux (restauration du brouillon), on recommence.
  await expect(async () => {
    await page.fill("#input", text);
    await page.click("#send", { timeout: 1000 });
  }).toPass({ timeout: 15_000 });
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

test("atelier : lanceur, schéma conseillé, équipe, suivi des étapes en direct", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.click("#navWs");
  await expect(page.locator("#wsLaunch")).toBeVisible();
  await expect(page.locator("#wlGo")).toBeDisabled();
  await page.fill("#wlText", "Faut-il héberger mes services à la maison ou chez un hébergeur ?");
  await expect(page.locator('.wl-pat.on[data-p="debate"]')).toBeVisible();          // conseillé et choisi : un débat
  await expect(page.locator(".wl-sug")).toHaveCount(1);
  await expect(page.locator("#wlTeam .wl-member")).toHaveCount(3);
  await expect(page.locator("#wlFlow .ws-node")).toHaveCount(3);
  await page.click('.wl-pat[data-p="review"]');                                    // choix manuel : rédaction puis relecture
  await page.click('#wlRounds button[data-r="2"]');
  await expect(page.locator("#wlFlow .ws-node")).toHaveCount(5);
  await expect(page.locator("#wlSum")).toContainText("5 appels");
  await page.click('.wl-pat[data-p="panel"]');
  await expect(page.locator("#wlFlow .ws-node")).toHaveCount(3);
  await page.click("#wlGo");
  await expect(page.locator("#wsLaunch")).toBeHidden();
  const msg = page.locator(".msg.atom").last();
  await expect(msg.locator(".ws-pipe .ws-node")).toHaveCount(3);
  await expect(msg.locator(".ws-node.done")).toHaveCount(3, { timeout: 20_000 });
  expect(errors).toEqual([]);
});

test("atelier : exemple en un clic et lancement au clavier (Ctrl+Entrée)", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  // Saisie puis menu « + » → Atelier : la demande est reprise. On recommence si la restauration du brouillon
  // a vidé la saisie entre-temps (machine lente).
  await expect(async () => {
    if (await page.locator("#wsLaunch").isVisible()) { await page.click("#wlClose"); await page.fill("#wlText", ""); }
    await page.fill("#input", "Ma demande depuis la saisie");
    await page.click("#toolsBtn");
    await page.locator("#toolsMenu").getByText("Atelier multi-IA…").click({ timeout: 2000 });
    await expect(page.locator("#wlText")).toHaveValue("Ma demande depuis la saisie", { timeout: 1500 });
  }).toPass({ timeout: 20_000 });
  await page.click('#wlEx [data-ex="1"]');
  await expect(page.locator("#wlText")).toHaveValue(/Compare SQLite/);
  await expect(page.locator('.wl-pat.on[data-p="panel"]')).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#wsLaunch")).toBeHidden();
  await page.click("#navWs");
  await expect(page.locator("#wlGo")).toBeEnabled();                              // configuration chargée
  await page.locator("#wlText").press("Control+Enter");
  await expect(page.locator("#wsLaunch")).toBeHidden();
  await expect(page.locator(".msg.atom").last().locator(".ws-node.done")).toHaveCount(3, { timeout: 20_000 });
  expect(errors).toEqual([]);
});

test("code : télécharger le fichier et voir l'aperçu d'une page HTML", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await send(page, "**index.html**\n\n```html\n<!doctype html><html><body><h1 id=\"t\">Bonjour Mint</h1></body></html>\n```");
  const block = page.locator(".msg.atom").last().locator(".code").first();
  await expect(block.locator(".code-h span")).toHaveText("index.html", { timeout: 15_000 });
  const [dl] = await Promise.all([page.waitForEvent("download"), block.locator("[data-dl]").click()]);
  expect(dl.suggestedFilename()).toBe("index.html");
  const content = require("fs").readFileSync(await dl.path(), "utf8");
  expect(content).toContain('<h1 id="t">Bonjour Mint</h1>');
  await block.locator("[data-preview]").click();
  await expect(page.locator("#pvw")).toBeVisible();
  await expect(page.frameLocator("#pvwFrame").locator("#t")).toHaveText("Bonjour Mint");
  await page.click('#pvw .seg button[data-w="390px"]');
  await expect(page.locator("#pvwFrame")).toHaveCSS("width", "390px");
  await page.keyboard.press("Escape");
  await expect(page.locator("#pvw")).toBeHidden();
  expect(errors).toEqual([]);
});

test("code : plusieurs fichiers → tout télécharger en .zip", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await send(page, "**index.html**\n\n```html\n<!doctype html><link rel=stylesheet href=style.css><h1>Zip</h1>\n```\n\n**style.css**\n\n```css\nh1 { color: #d32f2f; }\n```");
  const bar = page.locator(".msg.atom").last().locator(".zip-bar");
  await expect(bar).toContainText("2 fichiers", { timeout: 15_000 });
  await expect(bar).toContainText("style.css");
  const [dl] = await Promise.all([page.waitForEvent("download"), bar.locator("[data-zip]").click()]);
  expect(dl.suggestedFilename()).toBe("index.zip");
  // Le zip est valide et contient les deux fichiers complets (relu par Python).
  const out = require("child_process").execFileSync("python3", ["-c",
    "import sys,zipfile;z=zipfile.ZipFile(sys.argv[1]);assert z.testzip() is None;print('|'.join(n+':'+z.read(n).decode() for n in z.namelist()))",
    await dl.path()]).toString();
  expect(out).toContain("index.html:<!doctype html>");
  expect(out).toContain("style.css:h1 { color: #d32f2f; }");
  expect(errors).toEqual([]);
});

test("atelier : architecte en premier pour un livrable", async ({ page }) => {
  await login(page);
  await page.click("#navWs");
  await expect(page.locator("#wlGo")).toBeVisible();
  await page.fill("#wlText", "Crée une page web pour ma boulangerie à Lyon");
  await expect(page.locator("#wlFlow .ws-node").first()).toContainText("Architecte");
  await expect(page.locator("#wlArchNote")).toHaveText("cahier des charges d'abord");
  await page.click('#wlArch button[data-a="off"]');
  await expect(page.locator("#wlFlow .ws-node").first()).not.toContainText("Architecte");
  await page.click('#wlArch button[data-a="auto"]');
  await page.click('#wlRounds button[data-r="3"]');
  await expect(page.locator("#wlWarn")).toContainText("3 tours");
  await page.click('#wlRounds button[data-r="1"]');
  await page.click("#wlGo");
  const msg = page.locator(".msg.atom").last();
  await expect(msg.locator(".ws-node").first()).toContainText("Architecte");
  await expect(msg.locator(".ws-node.done")).toHaveCount(4, { timeout: 20_000 });
});

test("atelier : un clic à côté ne ferme pas la fenêtre, et les choix sont conservés", async ({ page }) => {
  await login(page);
  await page.click("#navWs");
  await expect(page.locator("#wlGo")).toBeVisible();
  await page.fill("#wlText", "Compare deux hébergeurs pour mon site");
  await page.click('.wl-pat[data-p="debate"]');
  await page.mouse.click(8, 8);                                                   // clic sur le fond assombri
  await expect(page.locator("#wsLaunch")).toBeVisible();
  await page.click("#wlClose");
  await expect(page.locator("#wsLaunch")).toBeHidden();
  await page.click("#navWs");                                                     // rouvert : rien n'est perdu
  await expect(page.locator("#wlText")).toHaveValue("Compare deux hébergeurs pour mon site");
  await expect(page.locator('.wl-pat.on[data-p="debate"]')).toBeVisible();
});

test("diagnostic complet : rapport copiable (NAS et Grafana simulés)", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.evaluate(() => openSettings("backup"));
  await page.click("#nasPush");                                                    // une copie, pour tester la restauration
  await expect(page.locator("#nasList li:not(.none)").first()).toBeVisible({ timeout: 15_000 });
  await page.evaluate(() => openSettings("status"));
  await page.click("#diagGo");
  await expect(page.locator("#diagOut")).toContainText("Diagnostic Atom", { timeout: 20_000 });
  await expect(page.locator("#diagOut")).toContainText("Copie sur NAS-VinX : ");
  await expect(page.locator("#diagOut")).toContainText("restauration testée");
  await expect(page.locator("#diagOut")).toContainText("panneaux sans erreur");
  await expect(page.locator("#diagCopy")).toBeVisible();
  expect(errors).toEqual([]);
});

test("fichiers d'une réponse → projet ouvert dans le mode Code", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  page.once("dialog", (d) => d.accept("Boulangerie e2e"));
  await send(page, "**index.html**\n\n```html\n<!doctype html><title>Ma boulangerie</title><h1>Pain</h1>\n```");
  const bar = page.locator(".msg.atom").last().locator(".zip-bar");
  await expect(bar).toContainText("1 fichier", { timeout: 15_000 });
  await bar.locator("[data-project]").click();
  await expect(page.locator("#title")).toHaveText("Code");
  await expect(page.locator("#cvProject option:checked")).toHaveText("Boulangerie e2e", { timeout: 15_000 });
  await expect(page.locator("#codeView")).toContainText("index.html");
  expect(errors).toEqual([]);
});

test("aperçu : versions successives et demande de modification", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await send(page, "**page.html**\n\n```html\n<!doctype html><h1 id=\"t\">Version un</h1>\n```");
  const block = page.locator(".msg.atom").last().locator(".code").first();
  await expect(block.locator("[data-preview]")).toBeVisible({ timeout: 15_000 });
  await block.locator("[data-preview]").click();
  await expect(page.frameLocator("#pvwFrame").locator("#t")).toHaveText("Version un");
  await expect(page.locator("#pvwVers button")).toHaveCount(0);                     // une seule version pour l'instant
  await page.fill("#pvwAskIn", "mets le titre en rouge");
  await page.click("#pvwAsk button[type=submit]");
  await expect(page.locator("#pvw")).toBeHidden();
  await expect(page.locator(".msg.user").last()).toContainText("Modifie le fichier **page.html**");
  // La réponse (modèle simulé) renvoie le fichier : deux versions dans la conversation.
  const last = page.locator(".msg.atom").last().locator(".code").first();
  await expect(last.locator("[data-preview]")).toBeVisible({ timeout: 15_000 });
  await last.locator("[data-preview]").click();
  await expect(page.locator("#pvwVers button")).toHaveCount(2);
  await expect(page.locator('#pvwVers button[data-v="1"]')).toHaveClass(/on/);
  await page.click('#pvwVers button[data-v="0"]');
  await expect(page.locator('#pvwVers button[data-v="0"]')).toHaveClass(/on/);
  expect(errors).toEqual([]);
});

test("brief du matin : réglages, aperçu et envoi", async ({ page }) => {
  const errors = watchErrors(page);
  await login(page);
  await page.evaluate(() => openSettings("brief"));
  await expect(page.locator("#brDays [data-d]")).toHaveCount(7);
  await page.fill("#brCity", "Lyon"); await page.locator("#brCity").blur();
  await expect(page.locator("#brCity")).toHaveValue("Lyon");
  await page.click('#brDays [data-d="6"]');                                       // dimanche décoché puis enregistré
  await expect(page.locator('#brDays [data-d="6"]')).toHaveAttribute("aria-pressed", "false");
  await page.click("#brPreview");
  await expect(page.locator("#brOut")).toContainText("Brief du");
  await expect(page.locator("#brOut")).toContainText("Lyon");
  await page.click("#brSend");
  await expect(page.locator("#convList")).toContainText("Brief du matin", { timeout: 5000 });
  expect(errors).toEqual([]);
});

test("tâche difficile : orchestration proposée, puis automatique", async ({ page }) => {
  test.setTimeout(420_000);
  const errors = watchErrors(page);
  await login(page);
  const hard = "Cherche les prix, puis compare-les, ensuite rédige une synthèse et enfin vérifie les calculs";
  await page.request.put("/api/hybrid", { data: { orchestrate: "suggest" }, headers: { "X-Atom": "1" } });
  await send(page, hard);
  const btn = page.locator(".msg.atom .orch-suggest").last();
  await expect(btn).toBeVisible({ timeout: 20_000 });                         // réponse directe, puis proposition
  await btn.click();
  await expect(page.locator(".ws-pipe").last()).toBeVisible({ timeout: 10_000 });   // relancée en orchestration
  await expect(page.locator("#send")).not.toHaveClass(/stop/, { timeout: 180_000 });   // orchestration terminée
  await page.request.put("/api/hybrid", { data: { orchestrate: "auto" }, headers: { "X-Atom": "1" } });
  const before = await page.locator(".ws-pipe").count();
  await send(page, hard);
  await expect(page.locator(".ws-pipe")).toHaveCount(before + 1, { timeout: 10_000 });   // directement orchestrée
  await expect(page.locator("#send")).not.toHaveClass(/stop/, { timeout: 180_000 });
  await page.request.put("/api/hybrid", { data: { orchestrate: "suggest" }, headers: { "X-Atom": "1" } });
  expect(errors).toEqual([]);
});

test("voix : dictée transcrite puis envoyée, lecture à voix haute", async ({ page }) => {
  const errors = watchErrors(page);
  // Pas de vrai micro en test : getUserMedia et MediaRecorder simulés, synthèse vocale espionnée.
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => ({ getTracks: () => [{ stop() {} }] });
    window.MediaRecorder = class {
      static isTypeSupported() { return true; }
      constructor() { this.state = "inactive"; this.mimeType = "audio/webm"; }
      start() { this.state = "recording"; }
      stop() { this.state = "inactive"; this.ondataavailable({ data: new Blob(["son"], { type: "audio/webm" }) }); this.onstop(); }
    };
    window.__spoken = [];
    window.speechSynthesis.speak = (u) => { window.__spoken.push(u.text); setTimeout(() => u.onend && u.onend(), 10); };
  });
  await login(page);
  await page.evaluate(() => { settings.voiceAutoSend = true; settings.voiceRead = true; saveSettings(); });
  await expect(page.locator("#micBtn")).toBeVisible();
  await page.click("#micBtn");
  await expect(page.locator("#micBtn")).toHaveClass(/rec/);
  await page.click("#micBtn");                                                    // fin de la dictée
  await expect(page.locator(".msg.user").last()).toContainText("dictée de test", { timeout: 15_000 });
  await expect(page.locator(".msg.atom").last()).toContainText("dictée de test", { timeout: 20_000 });
  await expect.poll(() => page.evaluate(() => window.__spoken.length), { timeout: 10_000 }).toBeGreaterThan(0);   // lue
  await page.locator('.msg.atom .acts [title="Lire à voix haute"]').last().click();
  await expect.poll(() => page.evaluate(() => window.__spoken.length)).toBeGreaterThan(1);
  expect(errors).toEqual([]);
});
