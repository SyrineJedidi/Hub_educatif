import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";

const credentials = JSON.parse(
  fs.readFileSync("../.local/browser.json", "utf8"),
);

test("contrôles de chaque champ Quiz et Question en création, modification et duplication", async ({
  page,
  context,
}) => {
  test.setTimeout(120000);
  async function post(path: string, body: unknown) {
    const csrf = (await (await context.request.get("/api/csrf/")).json())
      .csrfToken;
    return context.request.post("/api/" + path, {
      data: body,
      headers: { "X-CSRFToken": csrf },
    });
  }
  expect(
    (
      await post("auth/login/", {
        email: credentials.admin,
        password: credentials.password,
      })
    ).ok(),
  ).toBeTruthy();
  const teacher = (
    await (
      await context.request.get(
        "/api/admin/users/?q=" + encodeURIComponent(credentials.outsider),
      )
    ).json()
  ).results[0];
  const group = await (
    await post("groups/", {
      name: "Groupe contrôles de saisie",
      code: "VALID-" + Date.now(),
      teacher_id: teacher.id,
      level: "L1",
      academic_year: "2026",
    })
  ).json();
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (
      ["POST", "PATCH"].includes(request.method()) &&
      request.url().includes("/api/quizzes/")
    )
      mutations.push(request.url());
  });
  await page.goto("/administration/quiz/nouveau");
  await page.getByLabel("Titre du quiz").fill("   ");
  await page.getByLabel("Titre du quiz").press("Tab");
  await expect(page.getByLabel("Titre du quiz")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  const saveQuiz = page.getByRole("button", {
    name: "Enregistrer le brouillon",
    exact: true,
  });
  await saveQuiz.click();
  for (const label of [
    "Titre du quiz",
    "Description",
    "Niveau du quiz",
    "Durée du quiz",
    "Enseignant propriétaire",
    "Groupe pédagogique",
  ])
    await expect(page.getByLabel(label, { exact: true })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  await expect(page.getByLabel("Titre du quiz")).toBeFocused();
  expect(mutations).toEqual([]);
  await page.getByLabel("Titre du quiz").fill("   ");
  await page.getByLabel("Enseignant propriétaire").selectOption(teacher.id);
  await page.getByLabel("Groupe pédagogique").selectOption(group.id);
  await saveQuiz.click();
  await expect(page.getByLabel("Titre du quiz")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await page.getByLabel("Titre du quiz").fill("Quiz contrôlé");
  await expect(page.getByLabel("Titre du quiz")).not.toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await page
    .getByLabel("Description", { exact: true })
    .fill("Présentation du quiz contrôlé.");
  await page.getByLabel("Niveau du quiz").selectOption("EASY");
  await expect(page.getByLabel("Durée du quiz", { exact: true })).toHaveValue(
    "",
  );
  await page
    .getByLabel("Durée du quiz", { exact: true })
    .selectOption("unlimited");
  await expect(
    page.getByLabel("Durée du quiz", { exact: true }),
  ).not.toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("Durée en minutes")).toHaveCount(0);
  await page
    .getByLabel("Durée du quiz", { exact: true })
    .selectOption("limited");
  for (const [attempts, duration] of [
    ["11", "0"],
    ["2.5", "1e2"],
    ["", ""],
  ]) {
    await page.getByLabel("Tentatives autorisées").fill(attempts);
    await page.getByLabel("Durée en minutes").fill(duration);
    await saveQuiz.click();
    await expect(page.getByLabel("Tentatives autorisées")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    await expect(page.getByLabel("Durée en minutes")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  }
  expect(mutations).toEqual([]);
  await page.getByLabel("Tentatives autorisées").fill("2");
  await page.getByLabel("Durée en minutes").fill("10");
  let releaseSave!: () => void;
  const pendingSave = new Promise<void>((resolve) => {
    releaseSave = resolve;
  });
  await page.route("**/api/quizzes/", async (route) => {
    if (route.request().method() === "POST") await pendingSave;
    await route.continue();
  });
  await saveQuiz.click();
  await expect(
    page.getByRole("button", { name: "Veuillez patienter…", exact: true }),
  ).toBeDisabled();
  await page.locator("form").evaluate((form) => {
    form.dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true }),
    );
  });
  expect(mutations).toHaveLength(1);
  releaseSave();
  await expect(page).toHaveURL(/administration\/quiz\/[a-f0-9]{24}$/);
  const quizId = page.url().split("/").at(-1)!;
  await page.unroute("**/api/quizzes/");
  await page
    .getByRole("link", { name: "Modifier le brouillon", exact: true })
    .click();
  await page.getByLabel("Titre du quiz").fill(" ");
  await saveQuiz.click();
  await expect(page.getByLabel("Titre du quiz")).toBeFocused();
  expect(mutations).toHaveLength(1);
  await page.getByLabel("Titre du quiz").fill("Quiz contrôlé et modifié");
  await saveQuiz.click();
  await expect(page).toHaveURL(
    new RegExp("/administration/quiz/" + quizId + "$"),
  );
  await page
    .getByRole("link", { name: "Ajouter une question +", exact: true })
    .click();
  const saveQuestion = page.getByRole("button", {
    name: "Ajouter au brouillon",
    exact: true,
  });
  await saveQuestion.click();
  for (const label of [
    "Énoncé de la question",
    "Explication de correction",
    "Proposition A",
    "Proposition B",
    "Proposition C",
    "Proposition D",
  ])
    await expect(page.getByLabel(label, { exact: true })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  await expect(page.getByRole("radio").first()).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(page.getByLabel("Énoncé de la question")).toBeFocused();
  expect(mutations).toHaveLength(2);
  await page
    .getByLabel("Énoncé de la question")
    .fill("Combien font deux plus deux ?");
  for (const [letter, value] of [
    ["A", "4"],
    ["B", "  4  "],
    ["C", "3"],
    ["D", "5"],
  ])
    await page.getByLabel("Proposition " + letter, { exact: true }).fill(value);
  await page.getByRole("radio", { name: "A est la bonne réponse" }).check();
  await saveQuestion.click();
  await expect(page.getByLabel("Proposition B", { exact: true })).toBeFocused();
  await page.getByLabel("Proposition B", { exact: true }).fill("2");
  await page
    .getByLabel("Explication de correction")
    .fill("Deux plus deux font quatre.");
  for (const [points, position] of [
    ["11", "0"],
    ["1.5", "2.5"],
    ["", ""],
  ]) {
    await page.getByLabel("Points de la question").fill(points);
    await page.getByLabel("Position dans le quiz").fill(position);
    await saveQuestion.click();
    await expect(page.getByLabel("Points de la question")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    await expect(page.getByLabel("Position dans le quiz")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  }
  expect(mutations).toHaveLength(2);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((violation) => violation.id)).toEqual([]);
  fs.writeFileSync(
    "../docs/axe-quiz-validation.json",
    JSON.stringify(axe, null, 2),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/quiz-validation-mobile.png",
    fullPage: true,
  });
  await page.getByLabel("Points de la question").fill("3");
  await page.getByLabel("Position dans le quiz").fill("1");
  await saveQuestion.click();
  await expect(page).toHaveURL(
    new RegExp("/administration/quiz/" + quizId + "$"),
  );
  // Une position occupée est refusée par l’API et l’erreur reste attachée au champ.
  await page
    .getByRole("link", { name: "Ajouter une question +", exact: true })
    .click();
  await page
    .getByLabel("Énoncé de la question")
    .fill("Combien font un plus un ?");
  for (const [letter, value] of [
    ["A", "2"],
    ["B", "1"],
    ["C", "3"],
    ["D", "4"],
  ])
    await page.getByLabel("Proposition " + letter, { exact: true }).fill(value);
  await page.getByRole("radio", { name: "A est la bonne réponse" }).check();
  await page
    .getByLabel("Explication de correction")
    .fill("Un plus un font deux.");
  await page.getByLabel("Position dans le quiz").fill("1");
  await saveQuestion.click();
  await expect(page.getByLabel("Position dans le quiz")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(page.getByLabel("Position dans le quiz")).toBeFocused();
  await expect(page.getByLabel("Énoncé de la question")).toHaveValue(
    "Combien font un plus un ?",
  );
  await page.getByLabel("Position dans le quiz").fill("2");
  await saveQuestion.click();
  await expect(page).toHaveURL(
    new RegExp("/administration/quiz/" + quizId + "$"),
  );
  await page
    .getByRole("link", { name: "Modifier la question 1", exact: true })
    .click();
  await page.getByLabel("Proposition D", { exact: true }).fill(" 4 ");
  await page
    .getByRole("button", { name: "Enregistrer la question", exact: true })
    .click();
  await expect(
    page.getByLabel("Proposition D", { exact: true }),
  ).toHaveAttribute("aria-invalid", "true");
  await page.getByLabel("Proposition D", { exact: true }).fill("5");
  await page
    .getByLabel("Explication de correction")
    .fill("Deux plus deux font quatre.");
  await page
    .getByRole("button", { name: "Enregistrer la question", exact: true })
    .click();
  await expect(page).toHaveURL(
    new RegExp("/administration/quiz/" + quizId + "$"),
  );
  expect((await post("quizzes/" + quizId + "/publish/", {})).ok()).toBeTruthy();
  await page.goto("/administration/quiz/" + quizId + "/dupliquer");
  await page.getByLabel("Tentatives autorisées").fill("0");
  await page
    .getByRole("button", {
      name: "Dupliquer en nouveau brouillon",
      exact: true,
    })
    .click();
  await expect(page.getByLabel("Tentatives autorisées")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  // Le même formulaire est utilisé dans le front-office enseignant.
  await page.getByLabel("Tentatives autorisées").fill("2");
  await page
    .getByRole("button", {
      name: "Dupliquer en nouveau brouillon",
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(/administration\/quiz\/[a-f0-9]{24}$/);
  await context.clearCookies();
  expect(
    (
      await post("auth/login/", {
        email: credentials.outsider,
        password: credentials.password,
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto("/espace/quiz/nouveau");
  await saveQuiz.click();
  await expect(page.getByLabel("Titre du quiz")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(page.getByLabel("Groupe pédagogique")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(page.locator(".sidebar")).toHaveCount(0);
});
