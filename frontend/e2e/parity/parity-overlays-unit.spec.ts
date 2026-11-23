import { expect, test } from "@playwright/test";
import sharp from "sharp";

import { clearedShot, clearOverlays } from "./parityOverlays";

const HELD = `<!doctype html><html><body style="margin:0">
<nav id="rail" style="position:sticky;top:0;z-index:1;height:40px">Rail</nav>
<div id="aside" style="position:fixed;top:0;left:0;width:50px;height:50px"></div>
<div id="badge" style="position:fixed;bottom:0;left:150px;width:20px;height:20px"></div>
<div id="holder" style="position:sticky;top:0;margin-left:100px;width:200px">
  <figure id="fig" style="margin:0;height:600px">
    <header id="inner" style="position:sticky;top:0;height:20px">Inner</header>
  </figure>
</div>
<div style="height:2000px"></div>
</body></html>`;

const UNDER_RAIL = `<!doctype html><html><body style="margin:0">
<div style="height:100px"></div>
<nav style="position:sticky;top:0;z-index:1;height:40px;background:rgb(200,0,0)"></nav>
<figure id="fig" style="margin:0;height:600px;background:rgb(0,160,0)"></figure>
<div style="height:2000px"></div>
</body></html>`;

const SHORT = `<!doctype html><html><body style="margin:0">
<div style="height:100px"></div>
<nav style="position:sticky;top:0;z-index:1;height:40px;background:rgb(200,0,0)"></nav>
<h2 id="head" style="margin:0;height:30px;background:rgb(0,160,0)">Head</h2>
<div style="height:2000px"></div>
</body></html>`;

async function redPixels(image: Buffer): Promise<number> {
  const { data } = await sharp(image).removeAlpha().raw().toBuffer({ resolveWithObject: true });
  let count = 0;
  for (let at = 0; at < data.length; at += 3) if (data[at] > 180 && data[at + 1] < 40 && data[at + 2] < 40) count++;
  return count;
}

test("a capture scrolls its element up to the top, then down until the sticky and fixed bars over its top edge clear it, and names what it cleared and what still lies over it", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 300 });
  await page.setContent(HELD);
  const figure = await page.$("#fig");
  if (!figure) throw new Error("the page holds no figure");
  const place = await clearOverlays(figure);
  expect(place.cleared).toEqual(["rail"]);
  expect(place.over).toEqual(["badge"]);
  expect(place.scroll).toBe(0);
  expect(place.clip).toEqual({ x: 100, y: 40, width: 200, height: 600 });
  expect(place.fits).toBe(false);
  expect(await figure.evaluate((element) => element.getBoundingClientRect().top)).toBe(40);
});

test("a figure taller than the screen is captured without the sticky rail that lies over it in a plain capture", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 300 });
  await page.setContent(UNDER_RAIL);
  const figure = page.locator("#fig");
  const plain = await figure.screenshot({ animations: "disabled" });
  expect(await redPixels(plain), "the rail lies over the plain capture").toBeGreaterThan(0);
  const handle = await figure.elementHandle();
  if (!handle) throw new Error("the page holds no figure");
  const shot = await clearedShot(page, handle, { timeout: 5000, scale: "css" });
  if (!shot.image) throw new Error("the figure was not captured");
  expect(await sharp(shot.image).metadata()).toMatchObject({ width: 400, height: 600 });
  expect(await redPixels(shot.image), "the rail's red in the figure's capture").toBe(0);
  expect(shot.place?.cleared).toEqual(["nav"]);
});

test("a heading that fits on the screen once cleared is taken from the screen, below the rail", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 300 });
  await page.setContent(SHORT);
  const handle = await page.$("#head");
  if (!handle) throw new Error("the page holds no heading");
  const shot = await clearedShot(page, handle, { timeout: 5000, scale: "css" });
  expect(shot.place).toMatchObject({ fits: true, scroll: 100, clip: { x: 0, y: 140, width: 400, height: 30 }, view: { x: 0, y: 40, width: 400, height: 30 }, cleared: ["nav"] });
  if (!shot.image) throw new Error("the heading was not captured");
  expect(await sharp(shot.image).metadata()).toMatchObject({ width: 400, height: 30 });
  expect(await redPixels(shot.image)).toBe(0);
});
