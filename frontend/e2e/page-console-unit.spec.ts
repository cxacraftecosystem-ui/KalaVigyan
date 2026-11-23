import { expect, test, type Route } from "@playwright/test";

import { PageConsole } from "./production/pageConsole";

const OURS = "https://kalavigyan.test";
const CHALLENGES = "https://challenges.cloudflare.com";
const TURNSTILE_FRAME = `${CHALLENGES}/cdn-cgi/challenge-platform/h/g/turnstile/if/ov2/av0/rcv/0x4AAAAAAA/light/fbE/new/normal/auto/`;
const ORCHESTRATE = `${CHALLENGES}/cdn-cgi/challenge-platform/h/g/orchestrate/chl_api/v1`;
const TURNSTILE_CSP = "connect-src 'self' https://hagen.challenges.cloudflare.com https://brunhild.challenges.cloudflare.com";
const OUR_ERROR = "our sign-up page broke";
const FRAME_SCRIPT = 'console.error("%c%d", "font-size:0;color:transparent", NaN); fetch("data:,").catch(() => undefined);';

function ourPage(route: Route) {
  if (new URL(route.request().url()).pathname === "/app.js") {
    return route.fulfill({ contentType: "text/javascript", body: `console.error(${JSON.stringify(OUR_ERROR)});` });
  }
  return route.fulfill({ contentType: "text/html", body: `<!doctype html><html><body><iframe src="${TURNSTILE_FRAME}"></iframe><script src="/app.js"></script></body></html>` });
}

function turnstileFrame(route: Route) {
  if (route.request().url() === ORCHESTRATE) return route.fulfill({ contentType: "text/javascript", body: FRAME_SCRIPT });
  return route.fulfill({
    contentType: "text/html",
    headers: { "content-security-policy": TURNSTILE_CSP },
    body: `<!doctype html><html><body><script src="${ORCHESTRATE}"></script></body></html>`
  });
}

test("the console check counts our own page's errors and none from Cloudflare Turnstile's frame", async ({ page }) => {
  await page.route((url) => url.origin === OURS, ourPage);
  await page.route((url) => url.origin === CHALLENGES, turnstileFrame);
  const watch = new PageConsole(page, OURS);
  const seen: string[] = [];
  const problems: string[] = [];
  page.on("console", (message) => {
    seen.push(message.text());
    const problem = watch.problem(message);
    if (problem) problems.push(problem);
  });
  await page.goto(`${OURS}/signup`);
  await expect.poll(() => seen.some((text) => text.startsWith("Fetch API cannot load data:,"))).toBe(true);
  expect(seen).toContain("%c%d font-size:0;color:transparent NaN");
  expect(seen.some((text) => text.startsWith("Connecting to 'data:,' violates"))).toBe(true);
  expect(problems).toEqual([`console error: ${OUR_ERROR}`]);
  expect(watch.fromOurFrames(`${OURS}/app.js`)).toBe(true);
  expect(watch.fromOurFrames(ORCHESTRATE)).toBe(false);
  expect(watch.fromOurFrames("")).toBe(true);
});
