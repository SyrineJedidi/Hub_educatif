import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
const data = JSON.parse(fs.readFileSync("../.local/browser.json", "utf8"));
test("toutes les pages et les trois rôles : front-office Eduleb et back-office séparés", async ({
  page,
  context,
}) => {
  test.setTimeout(240000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const stamp = Date.now(),
    report: unknown[] = [];
  async function write(path: string, body: unknown, method = "POST") {
    const token = (await (await context.request.get("/api/csrf/")).json())
      .csrfToken;
    const response = await context.request.fetch("/api/" + path, {
      method,
      data: body,
      headers: { "X-CSRFToken": token },
    });
    expect(response.ok(), path + " " + response.status()).toBeTruthy();
    return response.json();
  }
  async function login(email: string) {
    await context.clearCookies();
    await write("auth/login/", { email, password: data.password });
  }
  await login(data.admin);
  const people = await (
    await context.request.get(
      "/api/admin/users/?q=" + encodeURIComponent(data.outsider),
    )
  ).json();
  const teacherId = people.results[0].id;
  const students = await (
    await context.request.get(
      "/api/admin/users/?q=" + encodeURIComponent(data.other_student),
    )
  ).json();
  const studentId = students.results[0].id;
  const group = await write("groups/", {
    name: "Atelier front-office " + stamp,
    code: "FRONT-" + stamp,
    level: "L2",
    academic_year: "2026–2027",
    teacher_id: teacherId,
  });
  await write("enrollments/", {
    student_id: studentId,
    group_id: group.id,
    starts_at: new Date(Date.now() - 86400000).toISOString(),
  });
  await login(data.outsider);
  const session = await write("sessions/", {
    group_id: group.id,
    title: "Séance front-office " + stamp,
    starts_at: new Date(Date.now() - 1800000).toISOString(),
    ends_at: new Date(Date.now() + 1800000).toISOString(),
    location: "Salle Nexora",
  });
  await write("sessions/", {
    group_id: group.id,
    title: "Prochaine rencontre " + stamp,
    starts_at: new Date(Date.now() + 86400000).toISOString(),
    ends_at: new Date(Date.now() + 90000000).toISOString(),
  });
  await write("sessions/" + session.id + "/sheet/", {});
  async function checkRoute(route: string, admin: boolean, width: number) {
    await page.goto(route);
    await expect(page.locator("main h1").first()).toBeVisible();
    await expect(
      page.getByRole("status").filter({ hasText: "Chargement en cours…" }),
    ).toHaveCount(0);
    if (admin) {
      await expect(page.locator(".workspace")).toHaveCount(1);
      if (width === 1440)
        await expect(page.locator("aside.sidebar")).toBeVisible();
      await expect(page.locator(".front-office")).toHaveCount(0);
    } else {
      await expect(page.locator(".front-office")).toHaveCount(1);
      await expect(page.locator(".front-study")).toHaveCount(1);
      await expect(
        page.locator(
          "aside,.sidebar,.workspace,.workspace-body,.workspace-top",
        ),
      ).toHaveCount(0);
      await expect(page.locator("header#navigation")).toBeVisible();
      await expect(page.locator(".footer")).toHaveCount(1);
      await expect(
        page.locator('header a[href^="/administration"]'),
      ).toHaveCount(0);
      const bounds = await page
        .locator(".front-study>.container")
        .boundingBox();
      expect(bounds!.width).toBeLessThanOrEqual(width);
      if (width === 1440) {
        expect(bounds!.x).toBeGreaterThan(0);
        expect(
          Math.abs(bounds!.x - (width - bounds!.x - bounds!.width)),
        ).toBeLessThan(3);
      }
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
      route,
    ).toBeTruthy();
    await page.reload();
    await expect(page.locator("main h1").first()).toBeVisible();
    expect(page.url()).toContain(route);
    report.push({
      route,
      width,
      layout: admin ? "back-office" : "front-office",
      reload: true,
      overflow: false,
    });
  }
  for (const [role, email] of [
    ["student", data.other_student],
    ["teacher", data.outsider],
    ["admin", data.admin],
  ]) {
    await login(email);
    const admin = role === "admin",
      base = admin ? "/administration" : "/espace";
    const home = admin
      ? base
      : base + (role === "student" ? "/etudiant" : "/enseignant");
    const routes = [
      home,
      base + "/groupes",
      base + "/groupes/" + group.id,
      base + "/seances",
      base + "/seances/" + session.id,
      base + "/assiduite",
      base + "/profil",
      base + "/quiz",
    ];
    if (role !== "student")
      routes.push(base + "/seances/" + session.id + "/appel");
    if (admin) routes.push(base + "/utilisateurs");
    for (const width of [1440, 390]) {
      await page.setViewportSize({
        width,
        height: width === 1440 ? 1000 : 844,
      });
      for (const route of routes) await checkRoute(route, admin, width);
      await page.goto(home);
      await expect(page.locator("main h1").first()).toBeVisible();
      if (!admin) {
        await expect(
          page.getByRole("link", { name: "Créer un compte", exact: true }),
        ).toHaveCount(0);
        await expect(
          page.getByRole("link", { name: "S’inscrire", exact: true }),
        ).toHaveCount(0);
        await page.screenshot({
          path: `../docs/screenshots/front-office-${role}-${width}.png`,
          fullPage: true,
        });
        await page.screenshot({
          path: `../docs/screenshots/front-office-${role}-${width}-viewport.png`,
        });
        if (width === 390) {
          await page.getByRole("button", { name: "Menu" }).click();
          await expect(
            page
              .getByRole("navigation", { name: "Navigation principale" })
              .getByRole("link", { name: "Accueil", exact: true }),
          ).toBeFocused();
          await page.keyboard.press("Escape");
          await expect(
            page.getByRole("button", { name: "Menu" }),
          ).toBeFocused();
        } else {
          const details = page.locator(".front-dropdown").filter({
            has: page.locator("summary").filter({ hasText: "Mes activités" }),
          });
          await details.locator("summary").focus();
          await page.keyboard.press("Enter");
          await expect(details).toHaveAttribute("open", "");
          await page.keyboard.press("Escape");
          await expect(details.locator("summary")).toBeFocused();
          await expect(details).not.toHaveAttribute("open", "");
        }
      } else
        await page.screenshot({
          path: `../docs/screenshots/back-office-admin-${width}.png`,
          fullPage: true,
        });
      const axe = await new AxeBuilder({ page }).analyze();
      fs.writeFileSync(
        `../docs/axe-layout-${role}-${width}.json`,
        JSON.stringify(axe, null, 2),
      );
      expect(
        axe.violations.map((v) => ({
          id: v.id,
          targets: v.nodes.map((n) => n.target),
        })),
      ).toEqual([]);
    }
    if (role === "teacher") {
      await page.goto(home);
      await page
        .getByRole("button", { name: "Créer une séance +", exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByLabel("Groupe", { exact: true })
        .selectOption(group.id);
      await page
        .getByLabel("Titre", { exact: true })
        .fill("Séance créée depuis l’accueil " + stamp);
      const local = (offset: number) =>
        new Date(Date.now() + offset + 3600000).toISOString().slice(0, 16);
      await page.getByLabel("Début (heure de Tunis)").fill(local(172800000));
      await page.getByLabel("Fin (heure de Tunis)").fill(local(176400000));
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "Enregistrer", exact: true })
        .click();
      await expect(page.getByRole("dialog")).not.toBeVisible();
      const sessions = await (
        await context.request.get("/api/sessions/?group=" + group.id)
      ).json();
      expect(
        sessions.results.some(
          (s: { title: string }) =>
            s.title === "Séance créée depuis l’accueil " + stamp,
        ),
      ).toBeTruthy();
    }
    // Existing profile form remains functional inside either shell.
    await page.goto(base + "/profil");
    const first = page.getByLabel("Prénom", { exact: true });
    const original = await first.inputValue();
    await first.fill(original + " Test");
    await first
      .locator("xpath=ancestor::form")
      .getByRole("button", { name: "Enregistrer", exact: true })
      .click();
    await expect(
      page.getByText("Enregistrement effectué.", { exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(first).toHaveValue(original + " Test");
    await first.fill(original);
    await first
      .locator("xpath=ancestor::form")
      .getByRole("button", { name: "Enregistrer", exact: true })
      .click();
    await expect(
      page.getByText("Enregistrement effectué.", { exact: true }),
    ).toBeVisible();
    if (!admin) {
      expect((await context.request.get("/api/admin/users/")).status()).toBe(
        403,
      );
      await page.goto("/administration/utilisateurs");
      await expect(page).toHaveURL(new RegExp(home + "$"));
      await page.goto(
        role === "student" ? "/espace/enseignant" : "/espace/etudiant",
      );
      await expect(page).toHaveURL(new RegExp(home + "$"));
      if (role === "student") {
        await page.goto("/espace/seances/" + session.id + "/appel");
        await expect(page).toHaveURL(
          new RegExp("/espace/seances/" + session.id + "$"),
        );
        expect(
          (
            await context.request.get("/api/sessions/" + session.id + "/sheet/")
          ).status(),
        ).toBe(403);
      }
      await page.goto("/");
      await expect(page.locator("header .front-profile")).toBeVisible();
      await expect(page.locator("aside")).toHaveCount(0);
    }
    await page.locator(".profile-menu summary").click();
    await page.getByRole("button", { name: "Se déconnecter" }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.waitForLoadState("load");
    await page.goto(base + "/profil");
    await expect(page).toHaveURL(/\/connexion$/);
  }
  fs.writeFileSync(
    "../docs/front-office-routes.json",
    JSON.stringify(report, null, 2),
  );
  expect(errors).toEqual([]);
});
