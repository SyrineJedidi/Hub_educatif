import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
const fixture = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));

test("résultats en lecture seule, enseignant propriétaire, administrateur et refus étudiant", async ({
  page,
  request,
  context,
}) => {
  test.setTimeout(150000);
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(30000);
  const errors: string[] = [],
    writes: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (
      ["POST", "PUT", "PATCH", "DELETE"].includes(request.method()) &&
      new URL(request.url()).pathname.startsWith("/api/quizzes/")
    )
      writes.push(request.url());
  });
  async function mutate(path: string, body: unknown, method = "POST") {
    const token = (await (await request.get("/api/csrf/")).json()).csrfToken;
    return request.fetch("/api/" + path, {
      method,
      data: body,
      headers: { "X-CSRFToken": token },
    });
  }
  expect(
    (
      await mutate("auth/login/", {
        email: fixture.admin,
        password: fixture.password,
      })
    ).ok(),
  ).toBeTruthy();
  const find = async (email: string) =>
    (
      await (
        await request.get("/api/admin/users/?q=" + encodeURIComponent(email))
      ).json()
    ).results[0];
  const owner = await find(fixture.outsider),
    otherTeacher = await find(fixture.teacher),
    student = await find(fixture.other_student);
  expect(
    (
      await mutate(
        `admin/users/${otherTeacher.id}/`,
        { role: "TEACHER" },
        "PATCH",
      )
    ).ok(),
  ).toBeTruthy();
  const groups = [];
  for (const [index, teacher] of [owner, otherTeacher].entries()) {
    const response = await mutate("groups/", {
      name: index ? "Groupe autre enseignant" : "Groupe Python résultats",
      code: `RESULT-${Date.now()}-${index}`,
      teacher_id: teacher.id,
      level: "L1",
      academic_year: "2026",
    });
    expect(response.status()).toBe(201);
    const group = await response.json();
    groups.push(group);
    expect(
      (
        await mutate("enrollments/", {
          student_id: student.id,
          group_id: group.id,
          starts_at: new Date(Date.now() - 86400000).toISOString(),
        })
      ).ok(),
    ).toBeTruthy();
  }
  const quizzes = [],
    questionSets = [];
  for (const [index, teacher] of [owner, otherTeacher].entries()) {
    const response = await mutate("quizzes/", {
      title: index ? "Quiz autre enseignant" : "Résultats Python",
      description: "Un quiz pour consulter les réponses.",
      teacher_id: teacher.id,
      learning_group_id: groups[index].id,
      level: "EASY",
      duration_minutes: null,
      max_attempts: 3,
    });
    expect(response.status()).toBe(201);
    const quiz = await response.json();
    quizzes.push(quiz);
    const questions = [];
    for (let number = 0; number < (index ? 1 : 2); number++) {
      const questionResponse = await mutate(`quizzes/${quiz.id}/questions/`, {
        statement: number
          ? "Quel mot-clé définit une classe ?"
          : "Quel mot-clé définit une fonction ?",
        choice_a: "def",
        choice_b: "class",
        choice_c: "print",
        choice_d: "return",
        correct_answer: number || index ? "B" : "A",
        explanation:
          number || index
            ? "class définit une classe."
            : "def définit une fonction.",
        points: index ? 2 : number ? 2 : 3,
      });
      expect(questionResponse.status()).toBe(201);
      questions.push(await questionResponse.json());
    }
    questionSets.push(questions);
    expect((await mutate(`quizzes/${quiz.id}/publish/`, {})).ok()).toBeTruthy();
  }
  expect(
    (
      await mutate("auth/login/", {
        email: fixture.other_student,
        password: fixture.password,
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await mutate(
        "profile/",
        { first_name: "Élodie", last_name: "Martin" },
        "PATCH",
      )
    ).ok(),
  ).toBeTruthy();
  const start = async (index: number) => {
    const response = await mutate(
      `student/quizzes/${quizzes[index].id}/attempts/`,
      {},
    );
    expect(response.status()).toBe(201);
    return response.json();
  };
  const save = async (id: string, question: string, choice: string) => {
    expect(
      (
        await mutate(
          `student/attempts/${id}/answers/${question}/`,
          { selected_choice: choice, expected_revision: 0 },
          "PUT",
        )
      ).ok(),
    ).toBeTruthy();
  };
  const closed = await start(0);
  for (const question of questionSets[0])
    await save(closed.id, question.id, "A");
  expect(
    (
      await mutate(`student/attempts/${closed.id}/submit/`, {
        answer_revisions: Object.fromEntries(
          questionSets[0].map((q) => [q.id, 1]),
        ),
      })
    ).ok(),
  ).toBeTruthy();
  const live = await start(0);
  await save(live.id, questionSets[0][1].id, "B");
  const other = await start(1);
  await save(other.id, questionSets[1][0].id, "B");
  expect(
    (
      await mutate(`student/attempts/${other.id}/submit/`, {
        answer_revisions: { [questionSets[1][0].id]: 1 },
      })
    ).ok(),
  ).toBeTruthy();
  async function login(email: string, admin = false) {
    await context.clearCookies();
    await page.goto("/connexion", { waitUntil: "domcontentloaded" });
    await page.getByLabel("Adresse email").fill(email);
    await page
      .getByLabel("Mot de passe", { exact: true })
      .fill(fixture.password);
    await page.getByRole("button", { name: /^Se connecter/ }).click();
    await expect(page).toHaveURL(
      admin ? /administration$/ : /espace\/(enseignant|etudiant)$/,
    );
  }
  await login(fixture.outsider);
  await page.goto(`/espace/quiz/${quizzes[0].id}`);
  await page
    .getByRole("link", { name: "Résultats des étudiants", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "2 tentative(s)", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".sidebar")).toHaveCount(0);
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  await expect(page.getByText("3 / 5", { exact: true })).toBeVisible();
  await expect(page.getByText("60 %", { exact: true })).toBeVisible();
  const liveRow = page.getByRole("row").filter({ hasText: "N° 2" });
  await expect(liveRow.getByText("En cours", { exact: true })).toHaveCount(2);
  await expect(liveRow.getByText(/%/)).toHaveCount(0);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => v.id)).toEqual([]);
  fs.writeFileSync(
    "../docs/axe-student-results-teacher.json",
    JSON.stringify(axe, null, 2),
  );
  await page.getByLabel("Rechercher un étudiant").fill("Introuvable");
  await expect(
    page.getByRole("heading", { name: "Aucun résultat", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Réinitialiser les filtres", exact: true })
    .click();
  await page.getByLabel("Rechercher un étudiant").fill("Martin Élodie");
  await page.getByLabel("Statut de la tentative").selectOption("SUBMITTED");
  await expect(
    page.getByRole("heading", { name: "1 tentative(s)", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Voir les réponses", exact: true })
    .click();
  await expect(page.getByText("3 / 5 points", { exact: true })).toBeVisible();
  await expect(
    page.getByText("def définit une fonction.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("class définit une classe.", { exact: true }),
  ).toBeVisible();
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/student-results-teacher-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.goto(`/espace/quiz/${quizzes[0].id}/resultats`);
  await page
    .getByRole("row")
    .filter({ hasText: "N° 2" })
    .getByRole("link", { name: "Voir les réponses", exact: true })
    .click();
  await expect(
    page.getByText("En cours — aucune note définitive.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText(/\d+ \/ 5 points/)).toHaveCount(0);
  expect(
    (await context.request.get(`/api/quizzes/results/${other.id}/`)).status(),
  ).toBe(404);
  await page.goto(`/espace/quiz/${quizzes[0].id}/resultats`);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "2 tentative(s)", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  const region = page.getByRole("region", {
    name: "Tentatives des étudiants",
    exact: true,
  });
  await region.focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(() => region.evaluate((el) => el.scrollLeft))
    .toBeGreaterThan(0);
  await region.evaluate((el) => {
    el.scrollLeft = 0;
  });
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/student-results-teacher-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(fixture.admin, true);
  await page
    .getByRole("link", { name: "Résultats des quiz", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "3 tentative(s)", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Quiz", { exact: true }).selectOption(quizzes[1].id);
  await page.getByLabel("Groupe", { exact: true }).selectOption(groups[1].id);
  await page
    .getByLabel("Enseignant", { exact: true })
    .selectOption(otherTeacher.id);
  await expect(
    page.getByRole("heading", { name: "1 tentative(s)", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("100 %", { exact: true })).toBeVisible();
  await page
    .getByRole("link", { name: "Voir les réponses", exact: true })
    .click();
  await expect(page.getByText("2 / 2 points", { exact: true })).toBeVisible();
  await expect(page.locator(".sidebar")).toBeVisible();
  const adminAxe = await new AxeBuilder({ page }).analyze();
  expect(adminAxe.violations.map((v) => v.id)).toEqual([]);
  fs.writeFileSync(
    "../docs/axe-student-results-admin.json",
    JSON.stringify(adminAxe, null, 2),
  );
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/student-results-admin-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/student-results-admin-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(fixture.teacher);
  await page.goto(`/espace/resultats-quiz/${closed.id}`);
  await expect(page.getByRole("alert")).toContainText("introuvable");
  await login(fixture.other_student);
  await page.goto(`/espace/resultats-quiz/${closed.id}`);
  await expect(page).toHaveURL(/\/espace\/quiz$/);
  expect(
    (await context.request.get(`/api/quizzes/results/${closed.id}/`)).status(),
  ).toBe(403);
  expect(
    (
      await context.request.get(`/api/student/attempts/${closed.id}/result/`)
    ).status(),
  ).toBe(200);
  await expect(
    page.getByRole("link", { name: "Résultats des étudiants", exact: true }),
  ).toHaveCount(0);
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});
