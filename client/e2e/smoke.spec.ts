import { expect, test } from "@playwright/test";

/** search, filter, register, login, save, apply, dashboard, logout - in one real browser session. */
test("a fresher can find, save and apply to a job", async ({ page, context }) => {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(String(error)));
  // Never actually visit an employer's site from a test.
  await context.route(
    (url) => !["localhost", "127.0.0.1"].includes(url.hostname),
    (route) => route.abort(),
  );

  // --- landing ---
  const home = await page.goto("/");
  const csp = home!.headers()["content-security-policy"];
  expect(csp).toContain("script-src 'self' 'nonce-");
  expect(csp).not.toContain("script-src 'self' 'unsafe-inline'");
  expect(csp).toContain("frame-ancestors 'none'");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("active fresher jobs")).toBeVisible();

  // --- search + URL-synced filter ---
  await page.getByRole("link", { name: "Browse jobs" }).first().click();
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.getByRole("status").filter({ hasText: /jobs? found/ })).toBeVisible();
  await page.getByLabel("Job type").selectOption({ index: 1 });
  await expect(page).toHaveURL(/type=/);
  await page.getByLabel("Title, company or skill").fill("zzzz-no-such-job-qqqq");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByRole("heading", { name: "No jobs match these filters" })).toBeVisible();
  await page.getByRole("link", { name: "Show all jobs" }).click();
  await expect(page).toHaveURL(/\/jobs$/);

  // --- detail ---
  const firstJob = page.locator("article h3 a").first();
  const title = (await firstJob.innerText()).trim();
  await firstJob.click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  const jobUrl = page.url();
  const apply = page.getByRole("link", { name: /Apply on company site/ });
  await expect(apply).toHaveAttribute("target", "_blank");
  await expect(apply).toHaveAttribute("rel", "noopener noreferrer");
  expect(await apply.getAttribute("href")).toMatch(/^https?:\/\//);

  // --- saving requires an account ---
  await page.getByRole("button", { name: "Save job" }).click();
  await expect(page).toHaveURL(/\/login\?next=/);

  // --- register, then log in ---
  const email = `e2e-${Date.now()}@example.com`;
  const password = "e2e test password 1";
  await page.getByRole("link", { name: "Create an account" }).click();
  await page.getByLabel("Full name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/login\?registered=1/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText(`Signed in as ${email}`)).toBeVisible();

  // The session cookie is HttpOnly: page scripts cannot read it, and nothing is in web storage.
  const cookies = await context.cookies();
  const session = cookies.find((c) => c.name.endsWith("SESSION"));
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Lax");
  expect(await page.evaluate(() => document.cookie)).not.toContain("SESSION");
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);

  // --- save ---
  await page.goto(jobUrl);
  await page.getByRole("button", { name: "Save job" }).click();
  await expect(page.getByRole("button", { name: /Saved/ })).toBeVisible();

  // --- apply: opens the employer's page in a new tab and records the click ---
  const [popup] = await Promise.all([
    context.waitForEvent("page"),
    page.getByRole("link", { name: /Apply on company site/ }).click(),
  ]);
  await popup.close();
  await expect(page.getByText("Opened in a new tab")).toBeVisible();

  // --- dashboard shows both ---
  await page.getByRole("link", { name: "Dashboard" }).click();
  await expect(page.getByRole("tabpanel").getByRole("link", { name: title })).toBeVisible();
  await page.getByRole("tab", { name: /Applied/ }).click();
  await expect(page.getByRole("tabpanel").getByRole("link", { name: title })).toBeVisible();

  // --- logout ---
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("link", { name: "Sign up" })).toBeVisible();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);

  expect(problems, "console errors / CSP violations").toEqual([]);
});
