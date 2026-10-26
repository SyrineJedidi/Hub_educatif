import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
const fixture = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));

test("passage, sauvegardes coordonnées, reprise, correction et reprise après archivage", async ({
  page,
  context,
  request,
}) => {
  test.setTimeout(150000);
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(30000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  async function post(path: string, body: unknown = {}) {
    const token = (await (await request.get("/api/csrf/")).json()).csrfToken;
    return request.post("/api/" + path, {
      data: body,
      headers: { "X-CSRFToken": token },
    });
  }
  expect(
    (
      await post("auth/login/", {
        email: fixture.admin,
        password: fixture.password,
      })
    ).ok(),
  ).toBeTruthy();
  const teacher = (
    await (
      await request.get(
        "/api/admin/users/?q=" + encodeURIComponent(fixture.outsider),
      )
    ).json()
  ).results[0];
  const student = (
    await (
      await request.get(
        "/api/admin/users/?q=" + encodeURIComponent(fixture.other_student),
      )
    ).json()
  ).results[0];
  const groupResponse = await post("groups/", {
    name: "Atelier passage Python",
    code: "ATT-" + Date.now(),
    teacher_id: teacher.id,
    level: "L1",
    academic_year: "2026",
  });
  expect(groupResponse.ok()).toBeTruthy();
  const group = await groupResponse.json();
  expect(
    (
      await post("enrollments/", {
        student_id: student.id,
        group_id: group.id,
        starts_at: new Date(Date.now() - 86400000).toISOString(),
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await post("auth/login/", {
        email: fixture.outsider,
        password: fixture.password,
      })
    ).ok(),
  ).toBeTruthy();
  const quiz = await (
    await post("quizzes/", {
      title: "Python en pratique",
      description: "Trois questions pour pratiquer Python.",
      level: "EASY",
      learning_group_id: group.id,
      duration_minutes: 10,
      max_attempts: 2,
    })
  ).json();
  const questions = [];
  for (const [index, answer] of ["A", "B", "C"].entries()) {
    const response = await post(`quizzes/${quiz.id}/questions/`, {
      statement: [
        "Quel mot-clé définit une fonction ?",
        "Quelle fonction compte les éléments ?",
        "Quel symbole commence une liste ?",
      ][index],
      choice_a: "def",
      choice_b: "len",
      choice_c: "[",
      choice_d: "class",
      correct_answer: answer,
      explanation: [
        "def définit une fonction.",
        "len compte les éléments.",
        "Les crochets délimitent les listes.",
      ][index],
      points: [3, 2, 1][index],
    });
    expect(response.status()).toBe(201);
    questions.push(await response.json());
  }
  expect((await post(`quizzes/${quiz.id}/publish/`)).ok()).toBeTruthy();
  await page.goto("/connexion");
  await page.getByLabel("Adresse email").fill(fixture.other_student);
  await page.getByLabel("Mot de passe", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: /^Se connecter/ }).click();
  await expect(page).toHaveURL(/espace\/etudiant$/);
  await page.goto(`/espace/quiz/${quiz.id}`);
  await page
    .getByRole("button", { name: "Commencer le quiz", exact: true })
    .click();
  await expect(page).toHaveURL(/espace\/tentatives\/[a-f0-9]{24}$/);
  const attemptId = page.url().split("/").at(-1)!;
  await expect(
    page.getByRole("heading", { name: "Python en pratique", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".sidebar")).toHaveCount(0);
  const safe = await (
    await context.request.get(`/api/student/attempts/${attemptId}/`)
  ).json();
  for (const forbidden of [
    "correct_answer",
    "explanation",
    "question_snapshot",
  ])
    expect(JSON.stringify(safe)).not.toContain(forbidden);
  expect(
    (
      await context.request.get(`/api/student/attempts/${attemptId}/result/`)
    ).status(),
  ).toBe(409);
  const q1 = page.getByRole("group", { name: /Question 1/ });
  const q2 = page.getByRole("group", { name: /Question 2/ });
  const q1Section = q1.locator("..");
  const q2Section = q2.locator("..");
  let releaseFirst!: () => void;
  const firstHold = new Promise<void>((resolve) => {
    releaseFirst = resolve;
  });
  let firstRequests = 0;
  const firstPattern = `**/api/student/attempts/${attemptId}/answers/${questions[0].id}/`;
  await page.route(firstPattern, async (route) => {
    firstRequests++;
    if (firstRequests === 1) await firstHold;
    await route.continue();
  });
  await q1.locator('input[value="A"]').check();
  await expect(
    q1Section.getByText("Enregistrement…", { exact: true }),
  ).toBeVisible();
  await q1.locator('input[value="B"]').check();
  expect(firstRequests).toBe(1);
  await expect(q1Section.getByText("Enregistré", { exact: true })).toHaveCount(
    0,
  );
  releaseFirst();
  await expect(
    q1Section.getByText("Enregistré", { exact: true }),
  ).toBeVisible();
  await expect(q1.locator('input[value="B"]')).toBeChecked();
  expect(firstRequests).toBe(2);
  await q1.locator('input[value="A"]').check();
  await expect(
    q1Section.getByText("Enregistré", { exact: true }),
  ).toBeVisible();
  let offline = true;
  const secondPattern = `**/api/student/attempts/${attemptId}/answers/${questions[1].id}/`;
  await page.route(secondPattern, async (route) => {
    if (offline) await route.abort();
    else await route.continue();
  });
  await q2.locator('input[value="A"]').focus();
  await page.keyboard.press("Space");
  await expect(
    q2Section.getByRole("button", { name: "Réessayer l’enregistrement" }),
  ).toBeVisible();
  await expect(q2.locator('input[value="A"]')).toBeChecked();
  await page
    .getByRole("button", { name: "Terminer ma tentative", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enregistrer et soumettre", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "La tentative n’a pas été soumise",
  );
  const stillOpen = await (
    await context.request.get(`/api/student/attempts/${attemptId}/`)
  ).json();
  expect(stillOpen.status).toBe("IN_PROGRESS");
  expect(stillOpen.answers).toHaveLength(1);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Fermer", exact: true })
    .click();
  offline = false;
  await q2Section
    .getByRole("button", { name: "Réessayer l’enregistrement" })
    .click();
  await expect(
    q2Section.getByText("Enregistré", { exact: true }),
  ).toBeVisible();
  await page.goto(`/espace/quiz/${quiz.id}`);
  await expect(
    page.getByText("Le passage et les tentatives seront proposés", {
      exact: false,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Commencer le quiz", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Reprendre", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/espace/tentatives/${attemptId}$`));
  await page.reload();
  await expect(q1.locator('input[value="A"]')).toBeChecked();
  await expect(q2.locator('input[value="A"]')).toBeChecked();
  await expect(
    page.getByText("2 / 3 questions répondues", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("timer")).toContainText(/Temps restant :/);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => v.id)).toEqual([]);
  fs.writeFileSync(
    "../docs/axe-quiz-attempt.json",
    JSON.stringify(axe, null, 2),
  );
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/quiz-attempt-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/quiz-attempt-mobile.png",
    fullPage: true,
  });
  await page.unroute(secondPattern);
  let releaseSave!: () => void;
  const saveHold = new Promise<void>((resolve) => {
    releaseSave = resolve;
  });
  await page.route(secondPattern, async (route) => {
    await saveHold;
    await route.continue();
  });
  let submissions = 0;
  page.on("request", (request) => {
    if (request.url().endsWith(`/attempts/${attemptId}/submit/`)) submissions++;
  });
  await q2.locator('input[value="B"]').check();
  await expect(
    q2Section.getByText("Enregistrement…", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Terminer ma tentative", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "1 question(s) sans réponse",
  );
  await page
    .getByRole("button", { name: "Enregistrer et soumettre", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Veuillez patienter…", exact: true }),
  ).toBeVisible();
  expect(submissions).toBe(0);
  releaseSave();
  await expect(page).toHaveURL(
    new RegExp(`/espace/tentatives/${attemptId}/resultat$`),
  );
  await expect(page.getByText("5 / 6 points", { exact: true })).toBeVisible();
  await expect(
    page.getByText("83,33 % de réussite", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("len compte les éléments.", { exact: true }),
  ).toBeVisible();
  const correctionAxe = await new AxeBuilder({ page }).analyze();
  expect(correctionAxe.violations.map((v) => v.id)).toEqual([]);
  fs.writeFileSync(
    "../docs/axe-quiz-result.json",
    JSON.stringify(correctionAxe, null, 2),
  );
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/quiz-result-mobile.png",
    fullPage: true,
  });
  const token = (await (await context.request.get("/api/csrf/")).json())
    .csrfToken;
  const repeat = await context.request.post(
    `/api/student/attempts/${attemptId}/submit/`,
    { data: { answer_revisions: {} }, headers: { "X-CSRFToken": token } },
  );
  expect((await repeat.json()).points_earned).toBe(5);
  await page.goto(`/espace/quiz/${quiz.id}`);
  await page
    .getByRole("link", { name: "Voir ma correction ↗", exact: true })
    .click();
  await expect(page.getByText("5 / 6 points", { exact: true })).toBeVisible();
  await page.goto(`/espace/quiz/${quiz.id}`);
  await page
    .getByRole("button", { name: "Commencer le quiz", exact: true })
    .click();
  await expect(page).toHaveURL(/espace\/tentatives\/[a-f0-9]{24}$/);
  const secondId = page.url().split("/").at(-1)!;
  expect(secondId).not.toBe(attemptId);
  expect((await post(`quizzes/${quiz.id}/archive/`)).ok()).toBeTruthy();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Python en pratique", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Mes tentatives ↗", exact: true })
    .click();
  await page.getByRole("link", { name: "Reprendre ↗", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/espace/tentatives/${secondId}$`));
  await page
    .getByRole("button", { name: "Terminer ma tentative", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enregistrer et soumettre", exact: true })
    .click();
  await expect(page.getByText("0 / 6 points", { exact: true })).toBeVisible();
  const limitedResponse = await post(`quizzes/${quiz.id}/duplicate/`, {
    title: "Quiz à tentative unique",
    max_attempts: 1,
    duration_minutes: null,
  });
  expect(limitedResponse.status()).toBe(201);
  const limited = await limitedResponse.json();
  expect((await post(`quizzes/${limited.id}/publish/`)).ok()).toBeTruthy();
  await page.goto(`/espace/quiz/${limited.id}`);
  await page
    .getByRole("button", { name: "Commencer le quiz", exact: true })
    .click();
  await expect(
    page.getByText("Durée illimitée", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Terminer ma tentative", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enregistrer et soumettre", exact: true })
    .click();
  await expect(page.getByText("0 / 6 points", { exact: true })).toBeVisible();
  await page.goto(`/espace/quiz/${limited.id}`);
  await expect(
    page.getByText("Limite de tentatives atteinte.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Commencer le quiz", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Voir ma correction ↗", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
