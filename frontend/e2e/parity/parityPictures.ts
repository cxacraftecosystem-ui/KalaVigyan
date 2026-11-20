import type { Page } from "@playwright/test";

export const PICTURE_WAIT_MS = 15_000;

export async function fullSizePictures(page: Page): Promise<void> {
  await page.evaluate(async (most) => {
    const images = [...document.querySelectorAll<HTMLImageElement>("img[srcset]")];
    for (const image of images) {
      image.removeAttribute("srcset");
      image.removeAttribute("sizes");
      image.loading = "eager";
    }
    const loaded = images.map((image) =>
      image.complete && image.currentSrc === image.src
        ? Promise.resolve()
        : new Promise<void>((resolve) => {
            image.addEventListener("load", () => resolve(), { once: true });
            image.addEventListener("error", () => resolve(), { once: true });
          })
    );
    await Promise.race([Promise.all(loaded), new Promise((resolve) => setTimeout(resolve, most))]);
  }, PICTURE_WAIT_MS);
}
