import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";

const fixture = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));
const phase = process.env.QUIZ_VISUAL_PHASE === "before" ? "before" : "after";
const output = `../docs/quiz-visual/${phase}`;
fs.mkdirSync(output, { recursive: true });

test("finition Quiz : écrans, langues, responsive, zoom et états accessibles", async ({
  page,
  request,
  context,
}) => {
  test.setTimeout(480000);
  page.setDefaultTimeout(15000);
  page.setDefaultNavigationTimeout(30000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  async function mutate(path: string, body: unknown = {}, method = "POST") {
    const token = (await (await request.get("/api/csrf/")).json()).csrfToken;
    return request.fetch(`/api/${path}`, {
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
  const user = async (email: string) =>
    (
      await (
        await request.get(`/api/admin/users/?q=${encodeURIComponent(email)}`)
      ).json()
    ).results[0];
  const owner = await user(fixture.outsider),
    student = await user(fixture.other_student);
  const created = await mutate("groups/", {
    name: "Informatique · Groupe A / المجموعة أ",
    code: `VIS-${Date.now()}`,
    teacher_id: owner.id,
    level: "L1",
    academic_year: "2026",
  });
  expect(created.status()).toBe(201);
  const group = await created.json();
  expect(
    (
      await mutate("enrollments/", {
        student_id: student.id,
        group_id: group.id,
        starts_at: new Date(Date.now() - 86400000).toISOString(),
      })
    ).ok(),
  ).toBeTruthy();
  const proposal = {
    statement: "Quelle instruction affiche une valeur en Python ?",
    choice_a: 'print("Bonjour")',
    choice_b: "input = 42",
    choice_c: "return sans fonction",
    choice_d: "delete variable",
    correct_answer: "A",
    explanation:
      "La fonction print affiche la valeur fournie. Les autres propositions ne correspondent pas à une instruction d’affichage.",
    notion: "Affichage et variables",
    points: 2,
  };
  async function quiz(title: string, published: boolean) {
    const response = await mutate("quizzes/", {
      title,
      description:
        "Consolidez les notions essentielles du cours : variables, instructions et conditions.\nPrenez le temps de lire chaque proposition avant de répondre.",
      teacher_id: owner.id,
      learning_group_id: group.id,
      level: "MEDIUM",
      duration_minutes: 20,
      max_attempts: 3,
      closes_at: new Date(Date.now() + 86400000).toISOString(),
    });
    expect(response.status()).toBe(201);
    const item = await response.json();
    item.questions = [];
    for (const [index, statement] of [
      proposal.statement,
      "Comment une variable conserve-t-elle une valeur ?",
      "متى نستخدم التعليمة الشرطية if في البرنامج؟",
    ].entries()) {
      const question = await mutate(`quizzes/${item.id}/questions/`, {
        ...proposal,
        statement,
        position: index + 1,
      });
      expect(question.status()).toBe(201);
      item.questions.push(await question.json());
    }
    if (published)
      expect((await mutate(`quizzes/${item.id}/publish/`)).ok()).toBeTruthy();
    return item;
  }
  const published = await quiz("Python : variables et conditions", true);
  const draft = await quiz(
    "Concevoir un programme clair et réutilisable",
    false,
  );
  await quiz("Premiers pas : consolider les bases", true);
  expect(
    (
      await mutate("auth/login/", {
        email: fixture.other_student,
        password: fixture.password,
      })
    ).ok(),
  ).toBeTruthy();
  const attempt = await (
    await mutate(`student/quizzes/${published.id}/attempts/`)
  ).json();
  const revisions: Record<string, number> = {};
  for (const [index, choice] of ["A", "B"].entries()) {
    const id = attempt.questions[index].id;
    const answer = await mutate(
      `student/attempts/${attempt.id}/answers/${id}/`,
      { selected_choice: choice, expected_revision: 0 },
      "PUT",
    );
    expect(answer.ok()).toBeTruthy();
    revisions[id] = 1;
  }
  expect(
    (
      await mutate(`student/attempts/${attempt.id}/submit/`, {
        answer_revisions: revisions,
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await mutate(
        `student/quizzes/${published.id}/feedback/`,
        {
          rating: "SUITABLE",
          comment: "Un parcours clair pour réviser. شرح مفيد وواضح.",
        },
        "PUT",
      )
    ).ok(),
  ).toBeTruthy();
  const running = await (
    await mutate(`student/quizzes/${published.id}/attempts/`)
  ).json();
  expect(
    (
      await mutate(
        `student/attempts/${running.id}/answers/${running.questions[0].id}/`,
        { selected_choice: "A", expected_revision: 0 },
        "PUT",
      )
    ).ok(),
  ).toBeTruthy();
  async function login(email: string) {
    await context.clearCookies();
    await page.goto("/connexion", { waitUntil: "domcontentloaded" });
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
  const routes = [
    {
      role: "teacher",
      email: fixture.outsider,
      pages: [
        ["list", "/espace/quiz"],
        ["quiz-form", `/espace/quiz/${draft.id}/modifier`],
        [
          "question-form",
          `/espace/quiz/${draft.id}/questions/${draft.questions[0].id}/modifier`,
        ],
        ["generation", `/espace/quiz/${draft.id}/generer`],
        ["preview", `/espace/quiz/${draft.id}/previsualisation`],
        ["results", `/espace/quiz/${published.id}/resultats`],
        ["answers", `/espace/resultats-quiz/${attempt.id}`],
      ],
    },
    {
      role: "student",
      email: fixture.other_student,
      pages: [
        ["list", "/espace/quiz"],
        ["presentation", `/espace/quiz/${published.id}`],
        ["attempt", `/espace/tentatives/${running.id}`],
        ["correction", `/espace/tentatives/${attempt.id}/resultat`],
        ["progress", "/espace/tentatives"],
      ],
    },
    {
      role: "admin",
      email: fixture.admin,
      pages: [
        ["list", "/administration/quiz"],
        ["quiz-form", `/administration/quiz/${draft.id}/modifier`],
        ["results", `/administration/quiz/${published.id}/resultats`],
      ],
    },
  ];
  const checks: unknown[] = [],
    accessibility: unknown[] = [];
  for (const role of routes) {
    await login(role.email);
    for (const language of phase === "before"
      ? ["fr", "ar"]
      : ["fr", "en", "ar"]) {
      await page.locator(".quiz-language select").selectOption(language);
      for (const width of phase === "before" ? [1440, 390] : [1440, 768, 390]) {
        await page.setViewportSize({ width, height: 1000 });
        for (const [name, path] of role.pages) {
          if (
            phase === "before" &&
            !["list", "quiz-form", "attempt", "correction", "results"].includes(
              name,
            )
          )
            continue;
          await page.goto(path);
          await expect(page.locator(".quiz-module").first()).toBeVisible();
          await page.waitForLoadState("networkidle");
          const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth + 1,
          );
          checks.push({ role: role.role, language, width, name, overflow });
          if (phase === "after")
            expect(
              overflow,
              `${role.role}/${name}/${language}/${width}`,
            ).toBeFalsy();
          if (
            ((language === "fr" && width === 1440) ||
              (language === "ar" && width === 390)) &&
            [
              "list",
              "quiz-form",
              "question-form",
              "attempt",
              "correction",
              "results",
              "progress",
              "generation",
            ].includes(name)
          ) {
            await page.screenshot({
              path: `${output}/${role.role}-${name}-${language}-${width}.png`,
              fullPage: true,
            });
          }
          if (
            phase === "after" &&
            width === 390 &&
            language !== "en" &&
            ["quiz-form", "attempt", "correction", "results"].includes(name)
          ) {
            const result = await new AxeBuilder({ page }).analyze();
            accessibility.push({
              role: role.role,
              language,
              name,
              violations: result.violations,
            });
            expect(
              result.violations,
              `${role.role}/${name}/${language}`,
            ).toHaveLength(0);
          }
        }
      }
    }
  }
  if (phase === "after") {
    await login(fixture.outsider);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/espace/quiz/nouveau");
    await page
      .getByRole("button", { name: "Enregistrer le brouillon", exact: true })
      .click();
    await expect(page.getByLabel("Titre du quiz")).toBeFocused();
    await expect(page.locator('[aria-invalid="true"]').first()).toBeVisible();
    await page.screenshot({
      path: `${output}/form-validation-focus.png`,
      fullPage: true,
    });
    await page.goto(`/espace/quiz/${draft.id}/generer`);
    const course =
      "print affiche une valeur. Une variable conserve une valeur.";
    await page.getByLabel("Texte du cours", { exact: true }).fill(course);
    let release: () => void = () => {};
    const responseReady = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route(
      `**/api/quizzes/${draft.id}/generate-questions/`,
      async (route) => {
        await responseReady;
        await route.fulfill({
          json: {
            questions: [
              proposal,
              {
                ...proposal,
                statement: "Quelle est la fonction d’une variable ?",
              },
              {
                ...proposal,
                statement: "Dans quel cas utiliser une condition ?",
              },
            ],
          },
        });
      },
    );
    await page
      .getByRole("button", { name: "Générer les propositions", exact: true })
      .click();
    await expect(
      page.getByLabel("Texte du cours", { exact: true }),
    ).toBeDisabled();
    await page.screenshot({
      path: `${output}/generation-loading-disabled.png`,
      fullPage: true,
    });
    release();
    await expect(page.locator("#quiz-ai-review")).toBeVisible();
    await page.screenshot({
      path: `${output}/generation-proposals.png`,
      fullPage: true,
    });
    const generated = await new AxeBuilder({ page }).analyze();
    expect(generated.violations).toHaveLength(0);
    accessibility.push({
      name: "generation-proposals",
      language: "fr",
      violations: generated.violations,
    });
    await page.locator(".quiz-language select").selectOption("ar");
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `${output}/generation-proposals-ar-390.png`,
      fullPage: true,
    });
    await login(fixture.other_student);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`/espace/tentatives/${running.id}`);
    const selected = page.locator(".quiz-taking-choice input:checked").first();
    await selected.focus();
    await page.keyboard.press("ArrowDown");
    await expect(
      page.locator(".quiz-taking-choice input:checked").first(),
    ).toBeFocused();
    await expect(
      page.getByText("Enregistré", { exact: true }).first(),
    ).toBeVisible();
    await page.screenshot({
      path: `${output}/attempt-keyboard-selected-focus.png`,
      fullPage: true,
    });
    const focused = await page
      .locator(".quiz-taking-choice:focus-within")
      .evaluate((element) => getComputedStyle(element).outlineStyle);
    expect(focused).not.toBe("none");
    // A separate context keeps Playwright's full-page capture and device metrics
    // consistent while reproducing the CSS viewport of 200% browser zoom.
    const zoomContext = await context.browser()!.newContext({
      baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:5174",
      viewport: { width: 720, height: 500 },
      deviceScaleFactor: 2,
      storageState: await context.storageState(),
    });
    const zoomPage = await zoomContext.newPage();
    await zoomPage.goto(`/espace/tentatives/${running.id}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(zoomPage.locator(".quiz-taking-choice").first()).toBeVisible();
    for (const language of ["fr", "ar"]) {
      await zoomPage.locator(".quiz-language select").selectOption(language);
      expect(await zoomPage.evaluate(() => innerWidth)).toBe(720);
      expect(await zoomPage.evaluate(() => devicePixelRatio)).toBe(2);
      expect(
        await zoomPage.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBeTruthy();
      await zoomPage.screenshot({
        path: `${output}/attempt-zoom-200-${language}.png`,
        fullPage: true,
      });
    }
    await zoomContext.close();
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page
        .locator(".quiz-taking-choice")
        .first()
        .evaluate((element) => getComputedStyle(element).transitionDuration),
    ).toBe("0s");
  }
  expect(errors).toEqual([]);
  fs.writeFileSync(
    `${output}/verification.json`,
    JSON.stringify(
      {
        phase,
        checks,
        accessibility,
        javascript_errors: errors,
        generation_api_simulated: phase === "after",
        zoom:
          phase === "after"
            ? "200% reflow emulation: 720 CSS px, DPR 2, 1440 px screen; FR and AR"
            : "not run",
      },
      null,
      2,
    ),
  );
});
