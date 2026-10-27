import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
const fixture = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));

test("dates, priorités, progression, retours, PDF et interface FR EN AR", async ({
  page,
  request,
  context,
}) => {
  test.setTimeout(240000);
  page.setDefaultTimeout(12000);
  page.setDefaultNavigationTimeout(30000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  async function mutate(path: string, body: unknown = {}, method = "POST") {
    const csrf = (await (await request.get("/api/csrf/")).json()).csrfToken;
    return request.fetch("/api/" + path, {
      method,
      data: body,
      headers: { "X-CSRFToken": csrf },
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
    student = await find(fixture.other_student);
  const groupResponse = await mutate("groups/", {
    name: "Groupe français عربي",
    code: "COMP-" + Date.now(),
    teacher_id: owner.id,
    level: "L1",
    academic_year: "2026",
  });
  expect(groupResponse.status()).toBe(201);
  const group = await groupResponse.json();
  expect(
    (
      await mutate("enrollments/", {
        student_id: student.id,
        group_id: group.id,
        starts_at: new Date(Date.now() - 86400000).toISOString(),
      })
    ).ok(),
  ).toBeTruthy();
  const question = {
    statement: "Énoncé français ORIGINAL — ما هي الإجابة؟",
    choice_a: "Option Alpha",
    choice_b: "Option Beta",
    choice_c: "Option Gamma",
    choice_d: "Option Delta",
    correct_answer: "B",
    explanation: "Explication pédagogique originale.",
    points: 2,
  };
  async function create(
    title: string,
    options: Record<string, unknown> = {},
    published = true,
  ) {
    const response = await mutate("quizzes/", {
      title,
      description: "Présentation pédagogique originale.",
      teacher_id: owner.id,
      learning_group_id: group.id,
      level: "EASY",
      duration_minutes: 20,
      max_attempts: 3,
      ...options,
    });
    expect(response.status()).toBe(201);
    const quiz = await response.json();
    const added = await mutate(`quizzes/${quiz.id}/questions/`, question);
    expect(added.status()).toBe(201);
    quiz.question = (await added.json()).id;
    if (published)
      expect((await mutate(`quizzes/${quiz.id}/publish/`)).ok()).toBeTruthy();
    return quiz;
  }
  const available = await create("Quiz disponible", {
    opens_at: new Date(Date.now() - 3600000).toISOString(),
    closes_at: new Date(Date.now() + 3600000).toISOString(),
  });
  const upcoming = await create("Quiz à venir", {
    opens_at: new Date(Date.now() + 3600000).toISOString(),
  });
  const closed = await create("Quiz fermé", {
    closes_at: new Date(Date.now() - 10000).toISOString(),
  });
  const ongoing = await create("Quiz à terminer");
  const draft = await create("Quiz brouillon", {}, false);
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
        { first_name: "مريم", last_name: "Été" },
        "PATCH",
      )
    ).ok(),
  ).toBeTruthy();
  expect(
    (await mutate(`student/quizzes/${ongoing.id}/attempts/`)).status(),
  ).toBe(201);
  expect(
    (await mutate(`student/quizzes/${closed.id}/attempts/`)).status(),
  ).toBe(400);
  expect(
    (await mutate(`student/quizzes/${upcoming.id}/attempts/`)).status(),
  ).toBe(400);
  async function login(email: string) {
    await context.clearCookies();
    await page.goto("/connexion");
    await page.locator(".quiz-language select").selectOption("fr");
    await page.getByLabel("Adresse email").fill(email);
    await page
      .getByLabel("Mot de passe", { exact: true })
      .fill(fixture.password);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(
      /administration$|espace\/(enseignant|etudiant)$/,
    );
  }
  await login(fixture.other_student);
  await expect(
    page.getByRole("heading", { name: "Mes quiz par priorité" }),
  ).toBeVisible();
  let progress = await (
    await request.get("/api/student/quiz-progress/")
  ).json();
  expect(progress.counts).toEqual({ to_start: 1, to_finish: 1, upcoming: 1 });
  await page.goto(`/espace/quiz/${upcoming.id}`);
  await expect(
    page.getByRole("button", { name: "Commencer le quiz", exact: true }),
  ).toHaveCount(0);
  await page.goto(`/espace/quiz/${available.id}`);
  await expect(page.getByText(/Temps disponible au départ/)).toBeVisible();
  await page
    .getByRole("button", { name: "Commencer le quiz", exact: true })
    .click();
  await expect(page).toHaveURL(/espace\/tentatives\/[a-f0-9]+$/);
  const attemptId = page.url().split("/").pop()!;
  const [saved] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.request().method() === "PUT" &&
        response.url().includes("/answers/"),
    ),
    page.locator("input[type=radio][value=B]").check(),
  ]);
  expect(saved.status()).toBe(200);
  await page
    .getByRole("button", { name: "Terminer ma tentative", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enregistrer et soumettre", exact: true })
    .click();
  await expect(page).toHaveURL(/\/resultat$/);
  const comment = "<script>window.feedbackExecuted=1</script> Très bien.";
  await page
    .getByLabel("Appréciation", { exact: true })
    .selectOption("SUITABLE");
  await page
    .getByLabel("Commentaire (facultatif)", { exact: true })
    .fill(comment);
  await page.locator(".quiz-language select").selectOption("en");
  await expect(
    page.getByRole("heading", {
      name: "Your result and correction",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Comment (optional)", { exact: true }),
  ).toHaveValue(comment);
  await page.locator(".quiz-language select").selectOption("ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(
    page.getByRole("heading", { name: "نتيجتك وتصحيحك", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(question.statement, { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("تعليق (اختياري)", { exact: true })).toHaveValue(
    comment,
  );
  await page.getByRole("button", { name: "حفظ رأيي", exact: true }).click();
  await expect(
    page.getByText("تم الحفظ بنجاح.", { exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => "feedbackExecuted" in window)).toBeFalsy();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByLabel("تعليق (اختياري)", { exact: true })).toHaveValue(
    comment,
  );
  await page.goto("/espace/tentatives");
  await expect(
    page.getByRole("heading", { name: "نتائجي", exact: true }),
  ).toBeVisible();
  progress = await (await request.get("/api/student/quiz-progress/")).json();
  expect(progress.completed_quizzes).toBe(1);
  expect(progress.remaining_quizzes).toBe(1);
  expect(progress.average_best_percentage).toBe(100);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  const axe = await new AxeBuilder({ page }).analyze();
  fs.writeFileSync(
    "../docs/axe-quiz-completion-ar.json",
    JSON.stringify({ violations: axe.violations }, null, 2),
  );
  expect(axe.violations).toHaveLength(0);
  await page.screenshot({
    path: "../docs/screenshots/quiz-completion-ar-student.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(fixture.outsider);
  await page.goto(`/espace/quiz/${available.id}/resultats`);
  await expect(
    page.getByRole("heading", { name: "Retours des étudiants", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(comment, { exact: true })).toBeVisible();
  expect(await page.evaluate(() => "feedbackExecuted" in window)).toBeFalsy();
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exporter les notes en PDF", exact: true })
    .click();
  await (await download).saveAs("../.local/quiz-completion-export.pdf");
  const paths = [
    `/espace/quiz`,
    `/espace/quiz/${draft.id}`,
    `/espace/quiz/${draft.id}/modifier`,
    `/espace/quiz/${draft.id}/questions/${draft.question}/modifier`,
    `/espace/quiz/${draft.id}/previsualisation`,
    `/espace/quiz/${draft.id}/generer`,
    `/espace/quiz/${available.id}/resultats`,
    `/espace/resultats-quiz/${attemptId}`,
  ];
  const routeChecks = [];
  for (const language of ["fr", "en", "ar"]) {
    await page.locator(".quiz-language select").selectOption(language);
    for (const path of paths) {
      await page.goto(path);
      await expect(page.locator("main h1")).toBeVisible();
      await expect(
        page.getByRole("heading", {
          name: "Cette page est introuvable",
          exact: true,
        }),
      ).toHaveCount(0);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
      ).toBeTruthy();
      routeChecks.push({ language, path });
    }
  }
  await page.goto(`/espace/quiz/${draft.id}/generer`);
  await page
    .getByLabel("نص الدرس", { exact: true })
    .fill("Contenu pédagogique à conserver.");
  await page.locator(".quiz-language select").selectOption("en");
  await expect(page.getByLabel("Course text", { exact: true })).toHaveValue(
    "Contenu pédagogique à conserver.",
  );
  await page.getByLabel("Course text", { exact: true }).fill("");
  await page
    .getByRole("button", { name: "Generate proposals", exact: true })
    .click();
  await expect(
    page.getByText("Paste the course text.", { exact: true }).first(),
  ).toBeVisible();
  await page.locator(".quiz-language select").selectOption("ar");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByText("ألصق نص الدرس.", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Paste the course text.", { exact: true }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/quiz-completion-ar-teacher.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(fixture.admin);
  await page.goto(`/administration/quiz/${available.id}/resultats`);
  await page.locator(".quiz-language select").selectOption("en");
  await expect(
    page.getByRole("heading", { name: "Student results", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".sidebar")).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/quiz-completion-admin.png",
    fullPage: true,
  });
  await page.locator(".quiz-language select").selectOption("ar");
  for (const width of [820, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBeTruthy();
  }
  expect(errors).toEqual([]);
  fs.writeFileSync(
    "../docs/quiz-completion-browser-verification.json",
    JSON.stringify(
      {
        routeChecks,
        language_persistence: true,
        unsaved_values_preserved: true,
        feedback_xss_executed: false,
        pdf_downloaded: true,
        progress: {
          completed: progress.completed_quizzes,
          remaining: progress.remaining_quizzes,
          average: progress.average_best_percentage,
        },
        javascript_errors: errors,
      },
      null,
      2,
    ),
  );
});
