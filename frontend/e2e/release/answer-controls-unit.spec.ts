import { expect, test } from "@playwright/test";

import { ANSWER_SCOPE } from "../production/gates";

import { ASK_OPTIONS, FILM_READY_MS, filmState, filmStateProblems, pictureCredits, segmentedChoices } from "./answerControls";

const PRESS = "for (const other of this.parentElement.querySelectorAll('button')) other.setAttribute('aria-pressed', String(other === this))";
const ASK_AGAIN = "window.askedAgain = (window.askedAgain || 0) + 1";

function group(label: string, choices: readonly string[], onPress: string): string {
  const buttons = choices.map((choice, at) => `<button type="button" aria-pressed="${at === 0}" onclick="${onPress}">${choice}</button>`).join("");
  return `<div class="kv-seg" role="group" aria-label="${label}">${buttons}</div>`;
}

function plate(title: string): string {
  return `<figure data-testid="media-plate"><p class="kv-credit">Photo: nevil zaveri, CC BY 2.0, via flickr.com · <a href="https://www.flickr.com/photos/${title}">${title}</a></p></figure>`;
}

test("the answer's choices are its own: the ask options above it, which ask the question again, are never pressed", async ({ page }) => {
  await page.setContent(
    `<main><div data-testid="ask-options">${group("Depth", ["Detailed", "Basic", "Expert"], ASK_AGAIN)}</div>` +
      `<article data-testid="answer-view">${group("Answer text", ["हिन्दी", "English"], PRESS)}</article></main>`
  );
  expect(await page.locator(`${ASK_OPTIONS} .kv-seg`).count()).toBe(1);
  expect(await segmentedChoices(page, ANSWER_SCOPE)).toEqual([]);
  expect(await page.evaluate(() => (window as Window & { askedAgain?: number }).askedAgain ?? 0)).toBe(0);
  expect(await page.locator('[aria-label="Answer text"] [aria-pressed="true"]').innerText()).toBe("हिन्दी");
});

test("the pictures read are the ones the reader sees in the answer, each credited and linked to its page", async ({ page }) => {
  await page.setContent(
    `<article data-testid="answer-view"><div style="display:none"><ul data-testid="image-strip"><li>${plate("dhamadka")}</li></ul></div>` +
      `<aside>${plate("dhamadka")}</aside></article>`
  );
  expect(await pictureCredits(page)).toEqual([]);
  await page.setContent(`<article data-testid="answer-view"><div style="display:none"><ul data-testid="image-strip"><li>${plate("dhamadka")}</li></ul></div></article>${plate("elsewhere")}`);
  expect(await pictureCredits(page)).toEqual(["The saved answer shows no pictures"]);
  await page.setContent(`<article data-testid="answer-view"><figure data-testid="media-plate"><p class="kv-credit">Photo: A</p></figure></article>`);
  expect(await pictureCredits(page)).toEqual(["Picture 1 shows no credit linked to its page"]);
});

test("the film is judged by the state it states, preparing, ready or failed with its reason, not by a clock", async ({ page }) => {
  const player = (inner: string) => `<div data-testid="film-player">${inner}</div>`;
  await page.setContent(player(`<div role="status" aria-label="Preparing the film"></div><button data-testid="film-play" aria-disabled="true" aria-label="Play">Play</button>`));
  expect(await filmState(page)).toBe("loading");
  expect(filmStateProblems(await filmState(page))).toEqual([`Film was still preparing its narration after ${FILM_READY_MS / 1000} s`]);
  await page.setContent(player(`<button data-testid="film-play" aria-label="Play">Play</button>`));
  expect(filmStateProblems(await filmState(page))).toEqual([]);
  const failed = `<div role="alert"><span><svg aria-hidden="true"></svg><span>Couldn't start the film. Try again.</span></span><button type="button">Try again</button></div>`;
  await page.setContent(player(`${failed}<button data-testid="film-play" aria-disabled="true" aria-label="Play">Play</button>`));
  expect(filmStateProblems(await filmState(page))).toEqual(["Film did not start: Couldn't start the film. Try again."]);
});
