import { test, expect } from "@playwright/test";
import fs from "node:fs";
const fixture = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));

test("Ollama réel : trois questions, révision, sélection et ajout confirmé", async ({
  page,
  request,
}) => {
  test.skip(
    process.env.RUN_OLLAMA_LIVE !== "1",
    "Appel local réel uniquement sur demande explicite.",
  );
  test.setTimeout(240000);
  page.setDefaultTimeout(15000);
  page.setDefaultNavigationTimeout(30000);
  const errors: string[] = [],
    directCalls: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (req) => {
    if (new URL(req.url()).port === "11434") directCalls.push(req.method());
  });
  async function post(path: string, body: unknown) {
    const token = (await (await request.get("/api/csrf/")).json()).csrfToken;
    return request.post(`/api/${path}`, {
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
  const owner = (
    await (
      await request.get(
        `/api/admin/users/?q=${encodeURIComponent(fixture.outsider)}`,
      )
    ).json()
  ).results[0];
  const groupResponse = await post("groups/", {
    name: "Atelier Qwen3",
    code: `QWEN-${Date.now()}`,
    teacher_id: owner.id,
    level: "L1",
    academic_year: "2026",
  });
  expect(groupResponse.status()).toBe(201);
  const group = await groupResponse.json();
  const quizResponse = await post("quizzes/", {
    title: "Quiz Python local",
    description: "Questions relues avant ajout.",
    teacher_id: owner.id,
    learning_group_id: group.id,
    level: "EASY",
    duration_minutes: null,
    max_attempts: 2,
  });
  expect(quizResponse.status()).toBe(201);
  const quiz = await quizResponse.json();
  await page.goto("/connexion");
  await page.getByLabel("Adresse email").fill(fixture.outsider);
  await page.getByLabel("Mot de passe", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/espace\/enseignant/);
  await page.goto(`/espace/quiz/${quiz.id}`);
  await page
    .getByRole("link", { name: "Générer des questions avec l’IA" })
    .click();
  await expect(
    page.getByText("IA locale — Qwen3 via Ollama", { exact: true }),
  ).toBeVisible();
  await page.reload({ waitUntil: "domcontentloaded" });
  await page
    .getByLabel("Texte du cours")
    .fill(
      "En Python, une variable associe un nom à une valeur. La fonction print() affiche du texte. Une liste conserve plusieurs éléments dans un ordre précis ; ses indices commencent à zéro. La fonction len() renvoie le nombre d’éléments d’une liste. La condition if exécute un bloc lorsque sa condition est vraie.",
    );
  await page.getByLabel("Nombre de questions").fill("3");
  await page.getByLabel("Niveau", { exact: true }).selectOption("EASY");
  const started = performance.now();
  const [generated] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().endsWith(`/quizzes/${quiz.id}/generate-questions/`) &&
        response.request().method() === "POST",
      { timeout: 190000 },
    ),
    page
      .getByRole("button", { name: "Générer les propositions", exact: true })
      .click(),
  ]);
  const duration = performance.now() - started;
  const body = await generated.json();
  expect(generated.status(), body.error?.message).toBe(200);
  expect(body.questions).toHaveLength(3);
  await expect(
    page.getByRole("region", { name: "Proposition 3", exact: true }),
  ).toBeVisible();
  expect(
    (await (await request.get(`/api/quizzes/${quiz.id}/questions/`)).json())
      .results,
  ).toHaveLength(0);
  expect(
    (await (await request.get(`/api/quizzes/${quiz.id}/`)).json()).status,
  ).toBe("DRAFT");
  const first = page.getByRole("region", {
    name: "Proposition 1",
    exact: true,
  });
  const editedPoints =
    body.questions[0].points < 10 ? body.questions[0].points + 1 : 9;
  await first.getByLabel("Points", { exact: true }).fill(String(editedPoints));
  await first
    .getByLabel("Notion", { exact: true })
    .fill("Notion relue par l’enseignant");
  await page
    .getByLabel("Sélectionner la proposition 3", { exact: true })
    .uncheck();
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: "../docs/screenshots/quiz-ollama-live.png",
    fullPage: true,
  });
  await page
    .getByRole("button", {
      name: "Ajouter les questions sélectionnées",
      exact: true,
    })
    .click();
  await expect(
    page.getByText("2 questions ajoutées. Le quiz reste en brouillon.", {
      exact: true,
    }),
  ).toBeVisible();
  const questions = (
    await (await request.get(`/api/quizzes/${quiz.id}/questions/`)).json()
  ).results;
  expect(questions).toHaveLength(2);
  expect(questions.map((q: { position: number }) => q.position)).toEqual([
    1, 2,
  ]);
  expect(questions[0]).toMatchObject({
    points: editedPoints,
    notion: "Notion relue par l’enseignant",
  });
  expect(questions.map((q: { statement: string }) => q.statement)).toEqual(
    body.questions.slice(0, 2).map((q: { statement: string }) => q.statement),
  );
  expect(
    (await (await request.get(`/api/quizzes/${quiz.id}/`)).json()).status,
  ).toBe("DRAFT");
  await page
    .getByRole("link", { name: "Vérifier les questions du quiz" })
    .click();
  await expect(
    page.getByText("Notion : Notion relue par l’enseignant", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  expect(directCalls).toEqual([]);
  fs.writeFileSync(
    "../docs/ollama-live-verification.json",
    JSON.stringify(
      {
        executed: true,
        model: "qwen3:8b",
        generation_seconds: Number((duration / 1000).toFixed(3)),
        generated: 3,
        saved_after_confirmation: 2,
        saved_before_confirmation: 0,
        status: "DRAFT",
        direct_browser_calls_to_ollama: 0,
        javascript_errors: errors,
        database_isolated: true,
      },
      null,
      2,
    ),
  );
});
