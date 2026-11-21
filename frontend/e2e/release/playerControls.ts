import type { Locator, Page } from "@playwright/test";

import { endsOnItsOwn, expectedProblems, nextDips, otherStep, unchangedProblems } from "./controlPlan";
import { changedFrom, reached, type ControlWatch } from "./controlWatch";

const QUICK_MS = 5_000;
const PLAY_MS = 9_000;
const MOLECULE_MS = 30_000;
const KIT_PLAYER = "figure.rp";
const ANSWER_PLAYER = '[data-testid="reaction-player"]';
const DIP_PLAYER = "figure.vat";
const CHOICE = '.seg[data-choice] button[data-v][aria-pressed="false"]';
const EXPERIMENT = '[data-x][aria-pressed="false"]';
const KIT_MOLECULE = ".mol[data-cid]";
const ANSWER_MOLECULE = '[data-testid="molecule-3d"]';

export type Present = { kit: boolean; answer: boolean };

function attribute(target: Locator, name: string): () => Promise<string> {
  return async () => (await target.getAttribute(name)) ?? "";
}

async function present(page: Page, kit: string, answer: string): Promise<Present> {
  return { kit: (await page.locator(kit).count()) > 0, answer: (await page.locator(answer).count()) > 0 };
}

async function pauseProblems(play: Locator, at: number, steps: number): Promise<string[]> {
  const pressed = attribute(play, "aria-pressed");
  if (endsOnItsOwn(at, steps)) return expectedProblems("the reaction player at its last step", "false", await reached(pressed, "false", QUICK_MS));
  await play.click();
  return expectedProblems("the reaction player's Pause", "false", await reached(pressed, "false", QUICK_MS));
}

export async function kitReactionPlayer(page: Page): Promise<string[]> {
  const player = page.locator(KIT_PLAYER).first();
  await player.scrollIntoViewIfNeeded();
  const step = attribute(player, "data-step");
  const steps = Number(await player.getAttribute("data-steps"));
  const target = otherStep(Number(await step()), steps);
  if (target === null) return [`the reaction player has ${steps} step`];
  const rail = player.locator(".rp-rail button");
  await rail.nth(target - 1).click();
  const chosen = await reached(step, String(target), QUICK_MS);
  await rail.first().click();
  const first = await reached(step, "1", QUICK_MS);
  const play = player.locator(".rp-play");
  await play.click();
  const playing = await reached(attribute(play, "aria-pressed"), "true", QUICK_MS);
  const moved = await changedFrom(step, first, PLAY_MS);
  return [
    ...expectedProblems(`the reaction player's step ${target}`, String(target), chosen),
    ...expectedProblems("the reaction player's first step", "1", first),
    ...expectedProblems("the reaction player's Play", "true", playing),
    ...unchangedProblems("the reaction player while playing", first, moved),
    ...(await pauseProblems(play, Number(moved), steps))
  ];
}

export async function answerReactionPlayer(page: Page): Promise<string[]> {
  const player = page.locator(ANSWER_PLAYER).first();
  await player.scrollIntoViewIfNeeded();
  const step = attribute(player, "data-step");
  const before = await step();
  if (before === "all") return ["the figure's reaction player shows every step at once and cannot be played"];
  await player.getByRole("button", { name: "Next step" }).click();
  const next = await changedFrom(step, before, QUICK_MS);
  await player.getByTestId("reaction-step").first().getByRole("button").click();
  const chosen = await reached(step, "1", QUICK_MS);
  await player.getByTestId("reaction-play").click();
  const pause = await player.getByTestId("reaction-pause").waitFor({ state: "visible", timeout: QUICK_MS }).then(
    () => [],
    () => ["the figure's reaction player shows no Pause after Play"]
  );
  const moved = await changedFrom(step, chosen, PLAY_MS);
  const pauseButton = player.getByTestId("reaction-pause");
  if (await pauseButton.isVisible()) await pauseButton.click();
  return [
    ...unchangedProblems("the figure's reaction player's Next step", before, next),
    ...expectedProblems("the figure's reaction player's first step", "1", chosen),
    ...pause,
    ...unchangedProblems("the figure's reaction player while playing", chosen, moved)
  ];
}

export async function dipPlayer(page: Page): Promise<string[]> {
  const player = page.locator(DIP_PLAYER).first();
  await player.scrollIntoViewIfNeeded();
  const dips = attribute(player, "data-dips");
  const before = Number(await dips());
  await player.locator(".vat-dip").click();
  const after = await reached(dips, String(nextDips(before)), QUICK_MS);
  return expectedProblems("the dip player", String(nextDips(before)), after);
}

async function pressPinned(page: Page, pinned: string, label: string): Promise<string[]> {
  const control = page.locator(pinned).first();
  await control.scrollIntoViewIfNeeded();
  await control.click();
  return expectedProblems(label, "true", await reached(attribute(control, "aria-pressed"), "true", QUICK_MS));
}

export async function whatIf(page: Page): Promise<string[]> {
  const problems: string[] = [];
  const experiment = page.locator(`${EXPERIMENT}:visible`).first();
  if (await experiment.count()) problems.push(...(await pressPinned(page, `[data-x="${await experiment.getAttribute("data-x")}"]`, "an experiment's tab")));
  const choice = page.locator(`${CHOICE}:visible`).first();
  if ((await choice.count()) === 0) return [...problems, "the document offers no what-if choice to press"];
  const group = await choice.evaluate((node) => node.closest("[data-choice]")?.getAttribute("data-choice") ?? "");
  const pinned = `.seg[data-choice="${group}"] button[data-v="${await choice.getAttribute("data-v")}"]`;
  return [...problems, ...(await pressPinned(page, pinned, "a what-if choice"))];
}

export async function kitMolecule(page: Page): Promise<string[]> {
  const molecule = page.locator(KIT_MOLECULE).first();
  await molecule.scrollIntoViewIfNeeded();
  const turned = attribute(molecule.locator(".mol-dial"), "aria-valuenow");
  await page.waitForTimeout(QUICK_MS / 5);
  const before = await turned();
  await molecule.locator(".mol-turn").click();
  const after = await changedFrom(turned, before, QUICK_MS);
  return unchangedProblems("the 3D molecule's Turn", before, after);
}

export async function answerMolecule(page: Page): Promise<string[]> {
  const molecule = page.locator(ANSWER_MOLECULE).first();
  await molecule.scrollIntoViewIfNeeded();
  const status = await reached(attribute(molecule, "data-status"), "ready", MOLECULE_MS);
  return expectedProblems("the figure's 3D molecule", "ready", status);
}

export async function playerSession(watch: ControlWatch, page: Page): Promise<void> {
  const reaction = await present(page, KIT_PLAYER, ANSWER_PLAYER);
  const molecule = await present(page, KIT_MOLECULE, ANSWER_MOLECULE);
  if (!reaction.kit && !reaction.answer) await watch.step("Reaction player", async () => ["the document draws no reaction player"]);
  if (reaction.kit) await watch.step("Reaction player steps and play", () => kitReactionPlayer(page));
  if (reaction.answer) await watch.step("Figure reaction player steps and play", () => answerReactionPlayer(page));
  await watch.step("Dip player", async () => ((await page.locator(DIP_PLAYER).count()) ? dipPlayer(page) : ["the document draws no dip player"]));
  if (molecule.kit) await watch.step("3D molecule turns", () => kitMolecule(page));
  if (molecule.answer) await watch.step("Figure 3D molecule reports ready", () => answerMolecule(page));
  if (!molecule.kit && !molecule.answer) await watch.step("3D molecule", async () => ["the document draws no 3D molecule"]);
}
