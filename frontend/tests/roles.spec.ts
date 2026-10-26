import { test, expect } from "@playwright/test";
import fs from "node:fs";
const data = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));
test("inscription étudiant ou enseignant et administrateur unique", async ({
  page,
  context,
}) => {
  const registered: string[] = [];
  for (const role of ["STUDENT", "TEACHER"]) {
    await context.clearCookies();
    await page.goto("/inscription");
    const select = page.getByLabel("Je suis", { exact: true });
    expect(
      await select
        .locator("option")
        .evaluateAll((options) =>
          options.map((o) => (o as HTMLOptionElement).value),
        ),
    ).toEqual(["", "STUDENT", "TEACHER"]);
    await page
      .getByLabel("Prénom", { exact: true })
      .fill(role === "TEACHER" ? "Professeure" : "Étudiante");
    await page.getByLabel("Nom", { exact: true }).fill("Nexora");
    const email = role.toLowerCase() + "-" + Date.now() + "@example.test";
    registered.push(email);
    await page.getByLabel("Adresse email").fill(email);
    await page.getByLabel("Mot de passe", { exact: true }).fill(data.password);
    await page.getByLabel("Confirmer le mot de passe").fill(data.password);
    expect(
      await select.evaluate((e) => (e as HTMLSelectElement).checkValidity()),
    ).toBe(false);
    await select.selectOption(role);
    await page.getByRole("button", { name: "Créer mon compte" }).click();
    await expect(page).toHaveURL(/connexion\?inscription=ok/);
    await page.getByLabel("Adresse email").fill(email);
    await page.getByLabel("Mot de passe", { exact: true }).fill(data.password);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(
      role === "TEACHER" ? /\/espace\/enseignant$/ : /\/espace\/etudiant$/,
    );
    expect(
      (await (await context.request.get("/api/auth/me/")).json()).user.role,
    ).toBe(role);
    expect((await context.request.get("/api/admin/users/")).status()).toBe(403);
    await expect(page.locator('header a[href^="/administration"]')).toHaveCount(
      0,
    );
    await page.locator(".profile-menu summary").click();
    await page.getByRole("button", { name: "Se déconnecter" }).click();
    await expect(page).toHaveURL(/\/$/);
  }
  await page.goto("/connexion");
  await page.getByLabel("Adresse email").fill(data.admin);
  await page.getByLabel("Mot de passe", { exact: true }).fill(data.password);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/administration$/);
  expect(
    (await (await context.request.get("/api/admin/users/?role=ADMIN")).json())
      .count,
  ).toBe(1);
  await page.goto("/administration/utilisateurs");
  await page.getByLabel("Rechercher par nom ou email").fill(registered[1]);
  await page.getByRole("button", { name: /Consulter et modifier/ }).click();
  expect(
    await page
      .getByLabel("Rôle attribué")
      .locator("option")
      .evaluateAll((options) =>
        options.map((o) => (o as HTMLOptionElement).value),
      ),
  ).toEqual(["STUDENT", "TEACHER"]);
  await page.getByRole("button", { name: "Fermer", exact: true }).click();
});
