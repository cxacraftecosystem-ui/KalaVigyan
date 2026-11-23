import type { ConsoleMessage, Frame, Page, Route } from "@playwright/test";

import { clip } from "./checks";
import { FRAME_DOCUMENT_START, type FrameSeen } from "./generatedExplainer";
import { requestFrame } from "./pageConsole";

const SRCDOC = "about:srcdoc";
const REFUSED = /\bRefused to\b/;
const FRAME_SELECTOR = 'iframe[data-testid="sandbox-frame"]';
const FRAME_RUN_MS = 3_000;

export type SandboxWatch = { requests: string[]; refusals: string[]; stop: () => Promise<void> };

function insideSandbox(frame: Frame | null): boolean {
  for (let current = frame; current; current = current.parentFrame()) {
    if (current.url().startsWith(SRCDOC)) return true;
  }
  return false;
}

export async function watchSandboxFrames(page: Page): Promise<SandboxWatch> {
  const watch: SandboxWatch = { requests: [], refusals: [], stop: async () => undefined };
  const handler = async (route: Route) => {
    if (!insideSandbox(requestFrame(route.request()))) return route.fallback();
    watch.requests.push(clip(route.request().url()));
    return route.abort("blockedbyclient");
  };
  const onConsole = (message: ConsoleMessage) => {
    if (message.location().url.startsWith(SRCDOC) && REFUSED.test(message.text())) watch.refusals.push(clip(message.text()));
  };
  await page.route("**/*", handler);
  page.on("console", onConsole);
  watch.stop = async () => {
    page.off("console", onConsole);
    await page.unroute("**/*", handler);
  };
  return watch;
}

export async function readSandboxFrames(page: Page): Promise<FrameSeen[]> {
  await page.waitForTimeout(FRAME_RUN_MS);
  const seen: FrameSeen[] = [];
  for (const element of await page.locator(FRAME_SELECTOR).elementHandles()) {
    const sandbox = await element.getAttribute("sandbox");
    const srcdoc = (await element.getAttribute("srcdoc")) ?? "";
    const frame = await element.contentFrame();
    const inside = frame
      ? await frame
          .evaluate(() => ({
            drawn: document.body !== null && document.body.childElementCount > 0 && document.body.getBoundingClientRect().height > 0,
            peerless: !("RTCPeerConnection" in window) && !("webkitRTCPeerConnection" in window)
          }))
          .catch(() => ({ drawn: false, peerless: false }))
      : { drawn: false, peerless: false };
    seen.push({ sandbox, policyFirst: srcdoc.startsWith(FRAME_DOCUMENT_START), ...inside });
  }
  return seen;
}
