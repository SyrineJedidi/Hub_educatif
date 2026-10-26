import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
const data = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));
const tunis = (minutes: number) =>
  new Date(Date.now() + minutes * 60000 + 3600000).toISOString().slice(0, 16);
test("scénario complet par rôle et protections API", async ({
  page,
  context,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  async function login(email: string) {
    await page.goto("/connexion");
    await page.getByLabel("Adresse email").fill(email);
    await page.getByLabel("Mot de passe", { exact: true }).fill(data.password);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(
      /administration$|espace\/(etudiant|enseignant)$/,
    );
  }
  async function logout() {
    await page.locator(".profile-menu summary").click();
    await page.getByRole("button", { name: "Se déconnecter" }).click();
    await expect(page).toHaveURL(/\/$/);
  }
  async function axe(label: string) {
    const r = await new AxeBuilder({ page }).analyze();
    fs.writeFileSync(`../docs/axe-${label}.json`, JSON.stringify(r, null, 2));
    expect(
      r.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.target),
      })),
    ).toEqual([]);
  }
  await page.goto("/inscription");
  await page.getByLabel("Prénom", { exact: true }).fill("Alice");
  await page.getByLabel("Nom", { exact: true }).fill("Nexora");
  await page.getByLabel("Je suis", { exact: true }).selectOption("STUDENT");
  await page.getByLabel("Adresse email").fill(data.student);
  await page.getByLabel("Mot de passe", { exact: true }).fill(data.password);
  await page.getByLabel("Confirmer le mot de passe").fill(data.password);
  await page.getByRole("button", { name: "Créer mon compte" }).click();
  await expect(page).toHaveURL(/connexion\?inscription=ok/);
  await login(data.student);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Mon espace", exact: true }),
  ).toBeVisible();
  await axe("student-dashboard");
  await page.screenshot({
    path: "../docs/screenshots/front-office-student-empty.png",
    fullPage: true,
  });
  await logout();
  await login(data.admin);
  await page.goto("/administration/utilisateurs");
  await page.getByLabel("Rechercher par nom ou email").fill(data.teacher);
  await page.getByRole("button", { name: /Consulter et modifier/ }).click();
  await page.getByLabel("Rôle attribué").selectOption("TEACHER");
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.goto("/administration/groupes");
  await page.getByRole("button", { name: "Créer un groupe" }).click();
  await page.getByLabel("Nom du groupe").fill("Groupe navigateur " + data.run);
  await page.getByLabel("Code unique").fill("NAV-" + data.run);
  await page.getByLabel("Niveau", { exact: true }).fill("L1");
  await page.getByLabel("Année universitaire").fill("2026–2027");
  await page
    .getByLabel("Enseignant responsable")
    .selectOption({ label: "Teacher " + data.run });
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Enregistrer", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("link", { name: "Groupe navigateur " + data.run, exact: true })
    .click();
  const groupId = page.url().split("/").at(-1)!;
  for (const email of [data.student, data.other_student]) {
    await page.getByRole("button", { name: "Inscrire un étudiant" }).click();
    await page.getByLabel("Étudiant actif").selectOption({
      label:
        (email === data.student
          ? "Alice Nexora"
          : "Other_Student " + data.run) +
        " · " +
        email,
    });
    await page.getByLabel("Entrée (heure de Tunis)").fill(tunis(-24 * 60));
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Enregistrer", exact: true })
      .click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
  }
  await axe("admin-group");
  await page.screenshot({
    path: "../docs/screenshots/admin-group.png",
    fullPage: true,
  });
  await logout();
  await login(data.teacher);
  await page.goto("/espace/seances");
  await page.getByRole("button", { name: "Créer une séance" }).click();
  await page
    .getByLabel("Groupe", { exact: true })
    .last()
    .selectOption({
      label:
        "Groupe navigateur " + data.run + " · NAV-" + data.run.toUpperCase(),
    });
  await page
    .getByLabel("Titre", { exact: true })
    .fill("Algorithmique navigateur");
  await page.getByLabel("Début (heure de Tunis)").fill(tunis(-35));
  await page.getByLabel("Fin (heure de Tunis)").fill(tunis(-5));
  await page
    .getByLabel("Salle ou lien de visioconférence")
    .fill("Salle Nexora");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Enregistrer", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("link", { name: /Ouvrir Algorithmique navigateur/ })
    .click();
  const sessionId = page.url().split("/").at(-1)!;
  await page.getByRole("link", { name: "Ouvrir la feuille d’appel" }).click();
  await page.getByRole("heading", { name: "2 participants" }).waitFor();
  await page.getByRole("button", { name: "Marquer tous présents" }).click();
  let sheet = await (
    await context.request.get("/api/sessions/" + sessionId + "/sheet/")
  ).json();
  expect(
    sheet.entries.every((e: { status: string }) => e.status === "UNSET"),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Enregistrer le brouillon" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Feuille enregistrée." }),
  ).toBeVisible();
  await page
    .getByLabel("Statut de Other_Student " + data.run)
    .selectOption("ABSENT");
  await page.getByRole("button", { name: "Valider la feuille" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Confirmer la validation" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Confirmer la validation" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Feuille validée." }),
  ).toBeVisible();
  await page.getByLabel("Statut de Alice Nexora").selectOption("LATE");
  await page
    .getByLabel("Motif obligatoire de la correction")
    .fill("Heure d’arrivée contrôlée");
  await page.getByRole("button", { name: "Enregistrer la correction" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Feuille enregistrée." }),
  ).toBeVisible();
  await axe("teacher-sheet");
  await page.screenshot({
    path: "../docs/screenshots/teacher-sheet.png",
    fullPage: true,
  });
  await page.goto("/espace/assiduite");
  await expect(page.getByText("50 %", { exact: true })).toBeVisible();
  await axe("teacher-statistics");
  await logout();
  await login(data.student);
  await page.goto("/espace/assiduite");
  await expect(page.getByText("100 %", { exact: true })).toBeVisible();
  await expect(page.getByText("Other_Student " + data.run)).not.toBeVisible();
  expect((await context.request.get("/api/admin/users/")).status()).toBe(403);
  expect((await context.request.get("/api/statistics/export/")).status()).toBe(
    403,
  );
  await axe("student-statistics");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../docs/screenshots/student-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await axe("student-statistics-mobile");
  await page.getByRole("button", { name: "Menu" }).click();
  await expect(
    page
      .getByRole("navigation", { name: "Navigation principale" })
      .getByRole("link", { name: "Accueil", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Menu" })).toBeFocused();
  await expect(
    page.getByRole("navigation", { name: "Navigation principale" }),
  ).not.toBeVisible();
  await logout();
  await login(data.outsider);
  expect(
    (await context.request.get("/api/groups/" + groupId + "/")).status(),
  ).toBe(403);
  expect(
    (
      await context.request.get("/api/statistics/export/?group=" + groupId)
    ).status(),
  ).toBe(403);
  await logout();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(data.admin);
  await page.goto("/administration/assiduite");
  await expect(page.getByText("50 %", { exact: true })).toBeVisible();
  await axe("admin-statistics");
  await page.screenshot({
    path: "../docs/screenshots/admin-statistics.png",
    fullPage: true,
  });
  await page.goto("/administration/seances/" + sessionId);
  await page.getByRole("button", { name: "Annuler la séance" }).click();
  await page.getByRole("button", { name: "Confirmer l’annulation" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(
    (
      await (
        await context.request.get("/api/statistics/?group=" + groupId)
      ).json()
    ).count,
  ).toBe(0);
  await logout();
  await login(data.teacher);
  await page.goto("/espace/seances/" + sessionId);
  await page
    .getByRole("link", { name: "Consulter la feuille historique" })
    .click();
  await expect(
    page.getByText(
      "Consultation de l’historique : la saisie est fermée pour cette séance.",
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Statut de Alice Nexora")).toBeDisabled();
  await expect(page.getByText("Heure d’arrivée contrôlée")).toBeVisible();
  expect(errors).toEqual([]);
});
