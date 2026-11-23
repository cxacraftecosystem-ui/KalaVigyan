import { expect, test, type Page } from "@playwright/test";
import sharp from "sharp";

import { hideOverlays, overlayFreeShot, showOverlays } from "./parityOverlays";

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

async function visibility(page: Page, id: string): Promise<string> {
  return page.evaluate((found) => getComputedStyle(document.getElementById(found) as Element).visibility, id);
}

async function redPixels(image: Buffer): Promise<number> {
  const { data } = await sharp(image).removeAlpha().raw().toBuffer({ resolveWithObject: true });
  let count = 0;
  for (let at = 0; at < data.length; at += 3) if (data[at] > 180 && data[at + 1] < 40 && data[at + 2] < 40) count++;
  return count;
}

test("a capture hides the sticky and fixed elements that lie over the figure, keeps those beside it, its own and those that hold it, and gives them back", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 300 });
  await page.setContent(HELD);
  await page.evaluate(() => window.scrollTo(0, 100));
  const figure = await page.$("#fig");
  if (!figure) throw new Error("the page holds no figure");
  expect(await hideOverlays(figure)).toEqual(["rail", "badge"]);
  expect(await Promise.all(["rail", "aside", "badge", "holder", "inner"].map((id) => visibility(page, id)))).toEqual(["hidden", "visible", "hidden", "visible", "visible"]);
  await showOverlays(figure);
  expect(await Promise.all(["rail", "badge"].map((id) => visibility(page, id)))).toEqual(["visible", "visible"]);
});

test("a figure taller than the screen is captured without the sticky rail that lies over it", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 300 });
  await page.setContent(UNDER_RAIL);
  const figure = page.locator("#fig");
  const plain = await figure.screenshot({ animations: "disabled" });
  expect(await redPixels(plain), "the rail lies over the plain capture").toBeGreaterThan(0);
  const shot = await overlayFreeShot(figure, 5000);
  if (!shot) throw new Error("the figure was not captured");
  expect(await redPixels(shot), "the rail's red in the figure's capture").toBe(0);
});
