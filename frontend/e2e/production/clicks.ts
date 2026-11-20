import type { Locator, Page } from "@playwright/test";

import { clip } from "./checks";
import { answersScript } from "./stuckPage";

const CLICK_TIMEOUT_MS = 30_000;
const ANSWER_TIMEOUT_MS = 5_000;
const STEADY_GAP_MS = 500;
const CALL_LOG_LINES = 6;

export async function clickProblems(page: Page, target: Locator, label: string): Promise<string[]> {
  const refused = await target.click({ timeout: CLICK_TIMEOUT_MS }).then(
    () => null,
    (error: unknown) => error
  );
  if (refused === null) return [];
  return [`${label} took no click in ${CLICK_TIMEOUT_MS / 1000} s`, ...(await clickDiagnosis(page, target, refused))];
}

async function clickDiagnosis(page: Page, target: Locator, error: unknown): Promise<string[]> {
  const log = callLog(error);
  const answers = await answersScript(page, ANSWER_TIMEOUT_MS);
  if (!answers) return [`the page ran no script for ${ANSWER_TIMEOUT_MS / 1000} s, so its main thread is stuck`, ...log];
  const before = await target.boundingBox();
  await page.waitForTimeout(STEADY_GAP_MS);
  const after = await target.boundingBox();
  const moved = JSON.stringify(before) !== JSON.stringify(after);
  const covering = await target.evaluate(coveringElement);
  return [clip(`box ${JSON.stringify(after)}${moved ? `, moved from ${JSON.stringify(before)}` : ", steady"}; at its centre: ${covering}`, 400), ...log];
}

function coveringElement(node: Element): string {
  const box = node.getBoundingClientRect();
  const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
  if (hit === null) return `nothing (viewport ${window.innerWidth}x${window.innerHeight})`;
  if (node.contains(hit)) return "the target itself";
  const marks = ["id", "data-testid", "aria-label", "role", "class"].map((name) => (hit.getAttribute(name) ? `${name}=${hit.getAttribute(name)}` : "")).filter(Boolean);
  return `<${hit.tagName.toLowerCase()} ${marks.join(" ")}>`;
}

function callLog(error: unknown): string[] {
  const message = error instanceof Error ? error.message : String(error);
  const lines = message.split("\n").map((line) => line.trim()).filter((line) => line.startsWith("- "));
  return lines.slice(-CALL_LOG_LINES).map((line) => clip(`call log ${line}`, 400));
}
