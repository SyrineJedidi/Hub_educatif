import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
test("accueil Eduleb, pages publiques, mobile et clavier", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("response", (response) => {
    if (
      response.status() >= 400 &&
      ["image", "font", "stylesheet", "script"].includes(
        response.request().resourceType(),
      )
    )
      errors.push(response.url());
  });
  fs.mkdirSync("../docs/screenshots", { recursive: true });
  for (const [name, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    await page.goto("http://127.0.0.1:8001/index.html");
    await page.waitForTimeout(1800);
    const documentHeight = await page.evaluate(
      () => document.documentElement.scrollHeight,
    );
    for (let y = 0; y < documentHeight; y += height - 100) {
      await page.evaluate((y) => window.scrollTo(0, y), y);
      await page.waitForTimeout(150);
    }
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo(0, 0));

    await page.screenshot({
      path: `../docs/screenshots/original-${name}.png`,
      fullPage: true,
    });
    await page.goto("/");
    await page
      .getByRole("heading", {
        name: "Vos cours prennent vie. Votre potentiel aussi.",
      })
      .waitFor();
    await page.screenshot({
      path: `../docs/screenshots/react-${name}.png`,
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    const axe = await new AxeBuilder({ page }).analyze();
    fs.writeFileSync(
      `../docs/axe-home-${name}.json`,
      JSON.stringify(axe, null, 2),
    );
    expect(
      axe.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.target),
      })),
    ).toEqual([]);
    if (name === "mobile") {
      await page.getByRole("button", { name: "Menu" }).click();
      await expect(
        page.getByRole("link", { name: "Connexion", exact: true }),
      ).toBeVisible();
      await page.getByRole("button", { name: "Menu" }).click();
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  for (const route of [
    "/connexion",
    "/inscription",
    "/mot-de-passe-oublie",
    "/reinitialiser-mot-de-passe?token=invalid",
    "/modules/quiz",
    "/inconnue",
  ]) {
    await page.goto(route);
    await page.locator("main h1, main h2").first().waitFor();
    const axe = await new AxeBuilder({ page }).analyze();
    expect(
      axe.violations.map((v) => ({
        route,
        id: v.id,
        nodes: v.nodes.map((n) => n.target),
      })),
    ).toEqual([]);
  }
  await page.goto("/connexion");
  await page.getByLabel("Adresse email").waitFor();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Aller au contenu" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Adresse email")).toBeFocused();
  expect(errors).toEqual([]);
});
