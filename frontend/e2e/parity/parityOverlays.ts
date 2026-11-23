import type { ElementHandle, Page, PageScreenshotOptions } from "@playwright/test";

export type ShotOptions = Pick<PageScreenshotOptions, "timeout" | "scale" | "type" | "quality">;
export type Clip = { x: number; y: number; width: number; height: number };
export type ClearedPlace = { clip: Clip; view: Clip; fits: boolean; cleared: string[]; over: string[]; scroll: number };
export type ClearedShot = { image: Buffer | null; place: ClearedPlace | null };

const EDGE = 1e-3;

export async function clearOverlays(target: ElementHandle<Element>): Promise<ClearedPlace> {
  return target.evaluate((element, edge) => {
    const overlays = (box: DOMRect) =>
      [...document.body.querySelectorAll("*")].filter((other) => {
        if (element.contains(other) || other.contains(element)) return false;
        const position = getComputedStyle(other).position;
        if (position !== "sticky" && position !== "fixed") return false;
        const rect = other.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && rect.left < box.right && rect.right > box.left && rect.top < box.bottom && rect.bottom > box.top;
      });
    const named = (other: Element) => {
      const classes = typeof other.className === "string" ? other.className.trim().split(/\s+/).filter(Boolean).slice(0, 2).join(".") : "";
      return `${other.id || other.tagName.toLowerCase()}${classes ? `.${classes}` : ""}`;
    };
    const base = Math.floor(element.getBoundingClientRect().top + window.scrollY + edge);
    window.scrollTo({ top: base, behavior: "instant" });
    const start = element.getBoundingClientRect();
    const covering = overlays(start).filter((other) => other.getBoundingClientRect().top <= start.top);
    const clear = Math.ceil(Math.max(0, ...covering.map((other) => other.getBoundingClientRect().bottom - start.top)) - edge);
    window.scrollTo({ top: base - Math.max(0, clear), behavior: "instant" });
    const box = element.getBoundingClientRect();
    const x = box.left + window.scrollX;
    const y = box.top + window.scrollY;
    const left = Math.floor(x + edge);
    const top = Math.floor(y + edge);
    const clip = { x: left, y: top, width: Math.ceil(x + box.width - edge) - left, height: Math.ceil(y + box.height - edge) - top };
    const view = { ...clip, x: clip.x - window.scrollX, y: clip.y - window.scrollY };
    const fits = view.x >= 0 && view.y >= 0 && view.x + view.width <= window.innerWidth && view.y + view.height <= window.innerHeight;
    return { clip, view, fits, cleared: covering.map(named), over: overlays(box).map(named), scroll: window.scrollY };
  }, EDGE);
}

export async function clearedShot(page: Page, target: ElementHandle<Element>, options: ShotOptions): Promise<ClearedShot> {
  const place = await clearOverlays(target).catch(() => null);
  if (!place || place.clip.width <= 0 || place.clip.height <= 0) return { image: null, place };
  const region = place.fits ? { clip: place.view } : { clip: place.clip, fullPage: true };
  const image = await page.screenshot({ ...options, ...region, animations: "disabled" }).catch(() => null);
  return { image, place };
}
