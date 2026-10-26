import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
const data = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));
test("quiz : conception complète, publication, confidentialité, duplication et archivage", async ({
  page,
  context,
}) => {
  test.setTimeout(240000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const cookies = new Map<
    string,
    Awaited<ReturnType<typeof context.cookies>>
  >();
  async function post(path: string, body: unknown = {}) {
    const csrf = (await (await context.request.get("/api/csrf/")).json())
      .csrfToken;
    return context.request.post("/api/" + path, {
      data: body,
      headers: { "X-CSRFToken": csrf },
    });
  }
  async function login(email: string) {
    await context.clearCookies();
    if (cookies.has(email)) {
      await context.addCookies(cookies.get(email)!);
      await page.goto(
        email === data.admin ? "/administration/quiz" : "/espace/quiz",
      );
      await expect(page.locator("main h1")).toBeVisible();
      return;
    }
    await page.goto("/connexion");
    await page.getByLabel("Adresse email").fill(email);
    await page.getByLabel("Mot de passe", { exact: true }).fill(data.password);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(
      /administration$|espace\/(etudiant|enseignant)$/,
    );
    cookies.set(email, await context.cookies());
  }
  async function axe(label: string) {
    const results = await new AxeBuilder({ page }).analyze();
    fs.writeFileSync(
      "../docs/axe-quiz-" + label + ".json",
      JSON.stringify(results, null, 2),
    );
    expect(
      results.violations.map((v) => ({
        id: v.id,
        targets: v.nodes.map((n) => n.target),
      })),
    ).toEqual([]);
  }
  const response = await post("auth/login/", {
    email: data.admin,
    password: data.password,
  });
  expect(response.ok()).toBeTruthy();
  cookies.set(data.admin, await context.cookies());
  const teacher = (
    await (
      await context.request.get(
        "/api/admin/users/?q=" + encodeURIComponent(data.outsider),
      )
    ).json()
  ).results[0];
  const student = (
    await (
      await context.request.get(
        "/api/admin/users/?q=" + encodeURIComponent(data.other_student),
      )
    ).json()
  ).results[0];
  const stamp = Date.now();
  const group = await (
    await post("groups/", {
      name: "Python · Atelier quiz " + stamp,
      code: "QZ-" + stamp,
      teacher_id: teacher.id,
      level: "L1",
      academic_year: "2026–2027",
    })
  ).json();
  expect(
    (
      await post("enrollments/", {
        student_id: student.id,
        group_id: group.id,
        starts_at: new Date(Date.now() - 86400000).toISOString(),
      })
    ).ok(),
  ).toBeTruthy();
  const outsider = "quiz-outsider-" + stamp + "@example.test";
  expect(
    (
      await post("auth/register/", {
        email: outsider,
        first_name: "Autre",
        last_name: "Étudiant",
        role: "STUDENT",
        password: data.password,
        confirmation: data.password,
      })
    ).status(),
  ).toBe(201);
  await login(data.outsider);
  await page.goto("/espace/quiz");
  await expect(
    page.getByRole("heading", { name: "Mes quiz", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Créer un quiz +", exact: true })
    .click();
  await page.getByLabel("Titre du quiz").fill("Les bases de Python");
  await page.getByRole("link", { name: "Annuler", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Quitter sans enregistrer ?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Continuer la saisie" }).click();
  await expect(page.getByLabel("Titre du quiz")).toHaveValue(
    "Les bases de Python",
  );
  await page
    .getByLabel("Description", { exact: true })
    .fill("Trois questions pour consolider les premières notions de Python.");
  await expect(page.getByLabel("Description", { exact: true })).toHaveValue(
    "Trois questions pour consolider les premières notions de Python.",
  );
  await page.goBack();
  await expect(
    page.getByRole("dialog", { name: "Quitter sans enregistrer ?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Continuer la saisie" }).click();
  await expect(page.getByLabel("Description", { exact: true })).toHaveValue(
    "Trois questions pour consolider les premières notions de Python.",
  );
  await page.getByLabel("Groupe pédagogique").selectOption(group.id);
  await page.getByLabel("Niveau du quiz").selectOption("EASY");
  await page
    .getByLabel("Durée du quiz", { exact: true })
    .selectOption("limited");
  await page.getByLabel("Durée en minutes").fill("10");
  await page.getByLabel("Tentatives autorisées").fill("2");
  await axe("quiz-form");
  await page.route("**/api/quizzes/", (route) =>
    route.request().method() === "POST" ? route.abort() : route.continue(),
  );
  await page.getByRole("button", { name: "Enregistrer le brouillon" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "serveur est injoignable",
  );
  await expect(page.getByLabel("Titre du quiz")).toHaveValue(
    "Les bases de Python",
  );
  await page.unroute("**/api/quizzes/");
  await page.getByRole("button", { name: "Enregistrer le brouillon" }).click();
  await expect(page).toHaveURL(/\/espace\/quiz\/[a-f0-9]{24}$/);
  const quizId = page.url().split("/").at(-1)!;
  const questions = [
    {
      statement: "Quel mot-clé définit une fonction en Python ?",
      choices: ["def", "class", "return", "import"],
      explanation: "",
      points: "2",
    },
    {
      statement: "Que renvoie len([1, 2, 3]) ?",
      choices: ["3", "2", "1", "0"],
      explanation: "La fonction len compte les trois éléments de la liste.",
      points: "3",
    },
    {
      statement: "Comment créer une liste vide ?",
      choices: ["[]", "{}", "()", "None"],
      explanation: "Les crochets représentent une liste Python.",
      points: "1",
    },
  ];
  for (let i = 0; i < questions.length; i++) {
    const q = questions[i];
    await page
      .getByRole("link", { name: "Ajouter une question +", exact: true })
      .click();
    await page.getByLabel("Énoncé de la question").fill(q.statement);
    for (let j = 0; j < 4; j++)
      await page
        .getByLabel("Proposition " + String.fromCharCode(65 + j), {
          exact: true,
        })
        .fill(q.choices[j]);
    await page
      .getByRole("radio", { name: "A est la bonne réponse", exact: true })
      .focus();
    await page.keyboard.press("Space");
    await expect(
      page.getByRole("radio", { name: "A est la bonne réponse", exact: true }),
    ).toBeChecked();
    await page.getByLabel("Points de la question").fill(q.points);
    await expect(page.getByLabel("Position dans le quiz")).toHaveValue(
      String(i + 1),
    );
    if (q.explanation)
      await page.getByLabel("Explication de correction").fill(q.explanation);
    if (i === 0) {
      await page.getByLabel("Proposition B", { exact: true }).fill("  DEF  ");
      await page.getByRole("button", { name: "Ajouter au brouillon" }).click();
      await expect(
        page.getByLabel("Proposition B", { exact: true }),
      ).toHaveAttribute("aria-invalid", "true");
      await expect(page.getByRole("alert")).toContainText("identique");
      await page.getByLabel("Proposition B", { exact: true }).fill("class");
      await axe("question-form");
    }
    if (!q.explanation) {
      await page.getByRole("button", { name: "Ajouter au brouillon" }).click();
      await expect(
        page.getByLabel("Explication de correction"),
      ).toHaveAttribute("aria-invalid", "true");
      await page
        .getByLabel("Explication de correction")
        .fill("Le mot-clé def commence la définition d’une fonction.");
    }
    await page.getByRole("button", { name: "Ajouter au brouillon" }).click();
    await expect(page).toHaveURL(new RegExp("/espace/quiz/" + quizId + "$"));
  }
  let presentation = await (
    await context.request.get("/api/quizzes/" + quizId + "/")
  ).json();
  expect(presentation.description).toBe(
    "Trois questions pour consolider les premières notions de Python.",
  );
  expect(presentation.question_count).toBe(3);
  expect(presentation.total_points).toBe(6);
  await page
    .getByRole("button", { name: "Descendre la question 1", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Monter la question 2", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Monter la question 2", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Descendre la question 1", exact: true }),
  ).toBeEnabled();
  await page.getByRole("link", { name: "Prévisualiser", exact: false }).click();
  await expect(
    page.getByRole("heading", { name: "Votre quiz est prêt à être publié" }),
  ).toBeVisible();
  await axe("preview");
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/quiz-teacher-preview-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await axe("preview-mobile");
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/quiz-teacher-preview-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("button", { name: "Publier le quiz", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Publier le quiz", exact: true }),
  ).toBeFocused();
  await page
    .getByRole("button", { name: "Publier le quiz", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirmer la publication", exact: true })
    .click();
  await expect(
    page.getByText("Ce quiz est verrouillé.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Ajouter une question +", exact: true }),
  ).toHaveCount(0);
  await login(data.other_student);
  await page.goto("/espace/quiz");
  await page
    .getByRole("link", { name: "Les bases de Python", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Les bases de Python", exact: true }),
  ).toBeVisible();
  const studentData = await (
    await context.request.get("/api/student/quizzes/" + quizId + "/")
  ).json();
  for (const forbidden of [
    "correct_answer",
    "explanation",
    "choice_a",
    "questions",
  ])
    expect(Object.hasOwn(studentData, forbidden)).toBe(false);
  await expect(page.getByText("Bonne réponse", { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Commencer le quiz", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".sidebar")).toHaveCount(0);
  expect(
    (
      await context.request.get("/api/quizzes/" + quizId + "/questions/")
    ).status(),
  ).toBe(403);
  await axe("student");
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/quiz-student-desktop.png",
    fullPage: true,
  });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Les bases de Python", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await axe("student-mobile");
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/quiz-student-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/espace/quiz/" + quizId + "/previsualisation");
  await expect(page).toHaveURL(/\/espace\/quiz$/);
  await page.goto(`/espace/quiz/${quizId}`);
  await page
    .getByRole("button", { name: "Commencer le quiz", exact: true })
    .click();
  await expect(page).toHaveURL(/espace\/tentatives\/[a-f0-9]{24}$/);
  for (let number = 1; number <= 3; number++) {
    const answerGroup = page.getByRole("group", {
      name: new RegExp(`^Question ${number}`),
    });
    await answerGroup.locator('input[value="A"]').check();
    await expect(
      answerGroup.locator("..").getByText("Enregistré", { exact: true }),
    ).toBeVisible();
  }
  await page
    .getByRole("button", { name: "Terminer ma tentative", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Enregistrer et soumettre", exact: true })
    .click();
  await expect(page.getByText("6 / 6 points", { exact: true })).toBeVisible();
  await login(outsider);
  expect(
    (
      await context.request.get("/api/student/quizzes/" + quizId + "/")
    ).status(),
  ).toBe(404);
  await login(data.admin);
  await page.goto("/administration/quiz");
  await page.getByLabel("Rechercher par titre").fill("Les bases de Python");
  await page.getByLabel("Enseignant", { exact: true }).selectOption(teacher.id);
  await page
    .getByRole("link", { name: "Les bases de Python", exact: true })
    .click();
  await expect(page.locator(".sidebar")).toBeVisible();
  await axe("admin");
  await page.locator("#main").focus();
  await page.screenshot({
    path: "../docs/screenshots/quiz-admin-desktop.png",
    fullPage: true,
  });
  await page.goto("/administration/quiz/nouveau");
  await page.getByLabel("Titre du quiz").fill("Titre".repeat(10));
  await page
    .getByLabel("Description", { exact: true })
    .fill("Présentation du quiz administrateur.");
  await page.getByLabel("Niveau du quiz").selectOption("MEDIUM");
  await page
    .getByLabel("Durée du quiz", { exact: true })
    .selectOption("unlimited");
  await page.getByLabel("Enseignant propriétaire").selectOption(teacher.id);
  await page.getByLabel("Groupe pédagogique").selectOption(group.id);
  await page.getByRole("button", { name: "Enregistrer le brouillon" }).click();
  await expect(page).toHaveURL(/administration\/quiz\/[a-f0-9]{24}$/);
  const adminDraftId = page.url().split("/").at(-1)!;
  expect(
    (
      await post("quizzes/" + adminDraftId + "/questions/", {
        statement: "Question".repeat(250),
        choice_a: "A".repeat(500),
        choice_b: "B".repeat(500),
        choice_c: "C".repeat(500),
        choice_d: "D".repeat(500),
        correct_answer: "B",
        explanation: "Correction détaillée.",
        points: 1,
      })
    ).status(),
  ).toBe(201);
  await page.reload();
  await page.locator(".quiz-statement").waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await axe("admin-mobile-long-content");
  await page.locator("#main").focus();
  await page.screenshot({ path: "../docs/screenshots/quiz-admin-mobile.png" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("button", { name: "Supprimer le brouillon", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirmer la suppression", exact: true })
    .click();
  await expect(page).toHaveURL(/administration\/quiz$/);
  await login(data.outsider);
  await page.goto("/espace/quiz/" + quizId);
  await page
    .getByRole("link", { name: "Dupliquer en brouillon", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Dupliquer en nouveau brouillon",
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(/espace\/quiz\/[a-f0-9]{24}$/);
  const duplicateId = page.url().split("/").at(-1)!;
  expect(duplicateId).not.toBe(quizId);
  presentation = await (
    await context.request.get("/api/quizzes/" + duplicateId + "/")
  ).json();
  expect(presentation.status).toBe("DRAFT");
  expect(presentation.question_count).toBe(3);
  expect(presentation.published_at).toBeNull();
  await page
    .getByRole("button", { name: "Supprimer la question 1", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirmer la suppression", exact: true })
    .click();
  expect(
    (await (await context.request.get("/api/quizzes/" + quizId + "/")).json())
      .question_count,
  ).toBe(3);
  await page
    .getByRole("button", { name: "Supprimer le brouillon", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirmer la suppression", exact: true })
    .click();
  await expect(page).toHaveURL(/espace\/quiz$/);
  await page.goto("/espace/quiz/" + quizId);
  await page.getByRole("button", { name: "Archiver", exact: true }).click();
  await page
    .getByRole("button", { name: "Confirmer l’archivage", exact: true })
    .click();
  await expect(page.getByText("Archivé", { exact: true })).toBeVisible();
  await login(data.other_student);
  expect(
    (
      await context.request.get("/api/student/quizzes/" + quizId + "/")
    ).status(),
  ).toBe(404);
  expect(errors).toEqual([]);
});
