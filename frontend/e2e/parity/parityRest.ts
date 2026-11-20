import type { BrowserContext, Page } from "@playwright/test";

export const VAT_PLAYED_KEY = "kv-vat-played";
export const LIVE_LINES = "#kv-main [role='status'], #kv-main [aria-live]";
export const PLAYING = "#kv-main .run, #kv-main .is-run, #kv-main .is-playing, #kv-main .hero[data-phase='in'], #kv-main .hero[data-phase='lifted'], #kv-main .hero[data-phase='air']";
export const QUIET_MS = 1000;
const MOST_MS = 15_000;
const POLL_MS = 200;

export type LiveSample = { at: number; lines: string; playing: number };

export function atRest(samples: readonly LiveSample[], quietMs: number = QUIET_MS): boolean {
  const last = samples[samples.length - 1];
  if (!last || last.playing > 0) return false;
  const changed = [...samples].reverse().find((sample) => sample.lines !== last.lines || sample.playing > 0);
  const since = changed ? samples[samples.indexOf(changed) + 1].at : samples[0].at;
  return last.at - since >= quietMs;
}

export async function restingVat(context: BrowserContext): Promise<void> {
  await context.addInitScript((key) => {
    try {
      sessionStorage.setItem(key, "1");
    } catch {
      return;
    }
  }, VAT_PLAYED_KEY);
}

async function sample(page: Page): Promise<LiveSample> {
  const found = await page.evaluate(
    ({ live, playing }) => ({
      lines: [...document.querySelectorAll<HTMLElement>(live)].map((node) => node.innerText.trim()).join("\n"),
      playing: document.querySelectorAll(playing).length
    }),
    { live: LIVE_LINES, playing: PLAYING }
  );
  return { at: Date.now(), ...found };
}

export async function playersAtRest(page: Page): Promise<boolean> {
  const samples: LiveSample[] = [await sample(page)];
  const start = Date.now();
  while (Date.now() - start < MOST_MS) {
    await page.waitForTimeout(POLL_MS);
    samples.push(await sample(page));
    if (atRest(samples)) return true;
  }
  return false;
}
