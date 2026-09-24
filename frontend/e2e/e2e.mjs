// End-to-end walk of every user flow in a real Chrome against `npm run dev` (MSW mock mode).
//   terminal 1:  npm run dev
//   terminal 2:  npm run e2e            (CHROME_PATH / BASE env vars override the defaults)
// Fails on any failed step, console error, page error, failed request or 5xx.
import fs from "node:fs";

import { chromium } from "playwright-core";

const BASE = process.env.BASE ?? "http://localhost:5174";
const SHOTS = new URL("./shots/", import.meta.url).pathname;
fs.mkdirSync(SHOTS, { recursive: true });
const results = [];
const problems = [];

const browser = await chromium.launch({
  timeout: 30000,
  executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome",
  args: ["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});

async function newPage(opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ...opts });
  const page = await ctx.newPage();
  page.setDefaultTimeout(25000);
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") problems.push(`[console.${m.type()}] ${m.text()}`);
  });
  page.on("pageerror", (e) => problems.push(`[pageerror] ${e.message}`));
  page.on("response", (r) => r.status() >= 500 && problems.push(`[http ${r.status()}] ${r.request().method()} ${r.url()}`));
  page.on("requestfailed", (r) => problems.push(`[requestfailed] ${r.url()} ${r.failure()?.errorText}`));
  return page;
}

async function step(name, fn) {
  const t = Date.now();
  try {
    await fn();
    results.push(`PASS ${name} (${Date.now() - t} ms)`);
    console.log(results.at(-1));
  } catch (e) {
    results.push(`FAIL ${name}: ${e.message.split("\n")[0]}`);
    console.log(results.at(-1));
  }
}
async function until(fn, msg, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (await fn().catch(() => false)) return;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(msg);
}
const expect = (cond, msg) => {
  if (!cond) throw new Error(msg);
};

const page = await newPage();

await step("home renders (title, nav, form, WebGL canvas)", async () => {
  await page.goto(BASE + "/");
  await page.getByRole("heading", { level: 1 }).waitFor();
  expect(await page.getByRole("link", { name: "Dashboard", exact: true }).isVisible(), "nav missing");
  expect(await page.getByLabel(/what's the problem/i).isVisible(), "textarea missing");
  await page.waitForTimeout(1500);
  expect((await page.locator("canvas").count()) === 1, "pulse-field canvas missing");
  await page.screenshot({ path: SHOTS + "01-home.png" });
});

await step("submit: empty form shows field errors, no request", async () => {
  let posted = 0;
  page.on("request", (r) => r.method() === "POST" && r.url().includes("/api/complaints") && posted++);
  await page.getByRole("button", { name: /submit report/i }).click();
  await page.getByText("Must be at least 10 characters.").waitFor();
  await page.getByText("Must be at least 3 characters.").waitFor();
  expect(posted === 0, "POST sent despite invalid form");
});

await step("submit: valid report → staged loading → AI result card", async () => {
  await page.getByLabel(/what's the problem/i).fill("Pani ka pipe burst ho gaya hai near the masjid, water on road");
  await page.getByLabel(/where/i).fill("Street 12, G-9/1, Islamabad");
  await page.getByLabel(/contact/i).fill("+92 300 1234567");
  await page.getByRole("button", { name: /submit report/i }).click();
  await page.getByRole("status").filter({ hasText: "Sending your report" }).waitFor();
  await page.getByText("Classifying with AI…").waitFor({ timeout: 4000 });
  const card = page.getByTestId("result");
  await card.waitFor({ timeout: 8000 });
  await page.waitForTimeout(900);
  const txt = await card.innerText();
  expect(/Water/.test(txt), "category not Water: " + txt);
  expect(/AI · groq/.test(txt), "provider badge missing");
  expect((await page.getByLabel(/what's the problem/i).count()) === 1, "form gone");
  expect((await page.getByLabel(/what's the problem/i).inputValue()) === "", "form not reset");
  const btn = page.getByRole("button", { name: /submit report/i });
  await btn.hover();
  await page.waitForTimeout(400);
  const bg = await btn.evaluate((e) => getComputedStyle(e).backgroundImage);
  expect(bg.includes("gradient"), "primary button loses its gradient on hover: " + bg);
  await page.screenshot({ path: SHOTS + "02-result.png" });
});

await step("submit: slow provider → 6 s copy → fallback badge", async () => {
  await page.getByRole("button", { name: /report another/i }).click();
  await page.getByLabel(/what's the problem/i).fill("Bijli ki taar gir gayi hai, bohat khatarnak, slow response");
  await page.getByLabel(/where/i).fill("G-10/4");
  await page.getByRole("button", { name: /submit report/i }).click();
  await page.getByText("The model is slow — we'll fall back to keyword rules if needed.").waitFor({ timeout: 8000 });
  await page.screenshot({ path: SHOTS + "03-slow.png" });
  const badge = page.locator('[data-testid="result"] [data-provider="rules:fallback"]');
  await badge.waitFor({ timeout: 6000 });
  expect((await badge.getAttribute("title")) === "AI provider unavailable; classified by keyword rules", "tooltip wrong");
  expect(/High/.test(await page.getByTestId("result").innerText()), "priority not High for 'khatarnak'");
  await page.screenshot({ path: SHOTS + "04-fallback.png" });
});

await step("dashboard: list, count, new report on top", async () => {
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await page.waitForURL(/\/dashboard/);
  await page.locator("li.complaint").first().waitFor();
  expect((await page.locator("li.complaint").count()) === 20, "page size 20 expected");
  await page.waitForTimeout(1600);
  const total = await page.locator(".total-pill").innerText();
  expect(/44 matching/.test(total), "total not 44 (42 seed + 2 new): " + total);
  expect(/taar gir gayi|Bijli/i.test(await page.locator("li.complaint").first().innerText()), "newest report not first");
  await page.screenshot({ path: SHOTS + "05-dashboard.png", fullPage: false });
});

await step("dashboard: multi-status filter → repeated params in URL, rows match", async () => {
  const f = page.getByRole("region", { name: "Filters" });
  await f.getByRole("button", { name: "Resolved", exact: true }).click();
  await f.getByRole("button", { name: "Rejected", exact: true }).click();
  await page.waitForURL(/status=resolved&status=rejected/);
  await until(async () => {
    const tags = await page.locator("li.complaint .complaint-tags").allInnerTexts();
    return tags.length > 0 && tags.every((t) => /Resolved|Rejected/.test(t));
  }, "filter leaked other statuses");
  await page.reload();
  await page.locator("li.complaint").first().waitFor();
  expect((await f.getByRole("button", { name: "Resolved", exact: true }).getAttribute("aria-pressed")) === "true", "filter lost on reload");
});

await step("dashboard: terminal complaint → 409 verbatim, buttons lock", async () => {
  const row = page.locator("li.complaint").filter({ hasText: "Resolved" }).first();
  await row.locator(".complaint-head").click();
  const group = row.getByRole("group", { name: "Move to status" });
  await group.getByRole("button", { name: /In progress/ }).click();
  const msg = /Invalid status transition: resolved -> in_progress\. 'resolved' is terminal\./;
  await page.getByRole("alert").filter({ hasText: msg }).waitFor();
  const btns = group.getByRole("button");
  for (let i = 0; i < (await btns.count()); i++) expect(await btns.nth(i).isDisabled(), "button not locked after terminal 409");
  await page.screenshot({ path: SHOTS + "06-409.png" });
  await page.getByRole("button", { name: /Clear 2 filters/ }).click();
  await page.waitForURL((u) => !u.search.includes("status"));
});

await step("dashboard: valid transition open → in_progress, then invalid in_progress → open", async () => {
  const f = page.getByRole("region", { name: "Filters" });
  await f.getByRole("button", { name: "Open", exact: true }).click();
  await page.waitForURL(/status=open/);
  await page.waitForTimeout(600);
  const row = page.locator("li.complaint").first();
  const id = (await row.locator(".complaint-meta .mono").innerText()).trim();
  await row.locator(".complaint-head").click();
  await row.getByRole("group", { name: "Move to status" }).getByRole("button", { name: /In progress/ }).click();
  await page.getByRole("status").filter({ hasText: `${id} is now in progress` }).waitFor();
  const tags = await row.locator(".complaint-tags").innerText();
  expect(/In progress/.test(tags), "row status not updated in place");
  await row.getByRole("group", { name: "Move to status" }).getByRole("button", { name: /^.?\s*Open$/ }).click();
  await page.getByRole("alert").filter({ hasText: "Invalid status transition: in_progress -> open." }).waitFor();
  await f.getByRole("button", { name: "Open", exact: true }).click();
});

await step("dashboard: pagination, sort, page size", async () => {
  await page.getByRole("button", { name: "Next →" }).click();
  await page.waitForURL(/page=2/);
  await until(async () => /Showing 21–40 of \d+/.test(await page.locator(".pager").innerText()), "pager text wrong: " + (await page.locator(".pager").innerText()));
  await page.getByLabel("Per page").selectOption("50");
  await page.waitForURL((u) => u.search.includes("page_size=50") && !u.search.includes("page=2"));
  await until(async () => {
    const total = Number((await page.locator(".pager").innerText()).match(/of (\d+)/)?.[1]);
    return total > 20 && (await page.locator("li.complaint").count()) === total;
  }, "page_size 50 should show every row");
  await page.getByLabel("Sort").selectOption("-priority");
  await until(async () => /High/.test(await page.locator("li.complaint .complaint-tags").first().innerText()), "priority sort wrong");
});

await step("dashboard: hand-edited junk URL is sanitised (no error)", async () => {
  await page.goto(BASE + "/dashboard?page_size=-9&sort=drop&status=closed&page=zz");
  await page.locator("li.complaint").first().waitFor();
  expect((await page.getByRole("alert").count()) === 0, "error banner shown for junk URL");
});

await step("stats: KPIs, 3 charts with all buckets, MISS then HIT", async () => {
  await page.getByRole("link", { name: "Pulse stats", exact: true }).click();
  await page.locator(".kpi").first().waitFor();
  await page.locator("[data-cache]").waitFor();
  expect((await page.locator("[data-cache]").getAttribute("data-cache")) === "MISS", "first load should be MISS");
  expect((await page.locator(".bar-row").count()) === 13, "expected 6+3+4 bars");
  await page.waitForTimeout(1600);
  await page.screenshot({ path: SHOTS + "07-stats.png", fullPage: true });
  await page.getByRole("button", { name: "Refresh now" }).click();
  await page.locator('[data-cache="HIT"]').waitFor();
  expect(/cached \d+ s ago/.test(await page.locator("[data-cache]").innerText()), "HIT copy wrong");
  await page.locator(".bar-row").first().hover();
  expect(await page.locator(".bar-row").first().locator(".bar-tip").isVisible(), "tooltip not visible on hover");
  await page.getByRole("button", { name: "Table" }).first().click();
  expect((await page.locator("table.data-table tbody tr").count()) === 6, "category table wrong");
  expect((await page.locator(".telemetry li").count()) > 0, "telemetry empty");
});

await step("stats: a write invalidates the cache (MISS again)", async () => {
  await page.getByRole("link", { name: "Report", exact: true }).click();
  await page.getByLabel(/what's the problem/i).fill("Kachra teen din se nahi uthaya gaya gali mein");
  await page.getByLabel(/where/i).fill("I-8/2");
  await page.getByRole("button", { name: /submit report/i }).click();
  await page.getByTestId("result").waitFor({ timeout: 9000 });
  await page.getByRole("link", { name: "Pulse stats", exact: true }).click();
  await page.locator("[data-cache]").waitFor();
  expect((await page.locator("[data-cache]").getAttribute("data-cache")) === "MISS", "cache not invalidated by POST");
});

await step("404 page + back link", async () => {
  await page.goto(BASE + "/nope/nothing");
  await page.getByText("This street isn't on our map.").waitFor();
  await page.getByRole("link", { name: "Report a problem" }).click();
  await page.waitForURL(BASE + "/");
});

await step("keyboard: tab reaches nav + form; focus ring visible", async () => {
  await page.goto(BASE + "/");
  await page.getByLabel(/what's the problem/i).waitFor();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  const tag = await page.evaluate(() => document.activeElement?.tagName);
  expect(tag === "A", "second Tab should land on a nav link, got " + tag);
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle);
  expect(outline !== "none", "no visible focus ring");
});

const mobile = await newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
await step("mobile 390px: no horizontal overflow on all pages", async () => {
  for (const [path, shot] of [["/", "08-m-home"], ["/dashboard", "09-m-dash"], ["/stats", "10-m-stats"]]) {
    await mobile.goto(BASE + path);
    await mobile.locator("h1").waitFor({ timeout: 30000 });
    await mobile.waitForTimeout(1800);
    const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow <= 1, `${path} overflows by ${overflow}px`);
    await mobile.screenshot({ path: SHOTS + shot + ".png" });
  }
});

const reduced = await newPage({ reducedMotion: "reduce" });
await step("reduced motion: titles render fully, no canvas animation errors", async () => {
  await reduced.goto(BASE + "/dashboard");
  await reduced.locator("li.complaint").first().waitFor({ timeout: 30000 });
  const h1 = await reduced.getByRole("heading", { level: 1 }).innerText();
  expect(h1.includes("Dashboard"), "decode text not settled under reduced motion: " + h1);
});

await browser.close();
// The 409 resource error is the browser logging the deliberate conflict flow.
const noisy = problems.filter((p) => !/Download the React DevTools|\[MSW\]|GL Driver Message|GPU stall|status of 409/.test(p));
console.log(results.join("\n"));
console.log(`\n${results.filter((r) => r.startsWith("PASS")).length}/${results.length} passed`);
console.log(noisy.length ? `\nBrowser problems (${noisy.length}):\n` + [...new Set(noisy)].join("\n") : "\nNo console errors, page errors or failed requests.");
process.exit(results.some((r) => r.startsWith("FAIL")) || noisy.length ? 1 : 0);
