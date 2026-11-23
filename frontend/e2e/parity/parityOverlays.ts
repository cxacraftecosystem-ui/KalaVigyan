import type { ElementHandle, Locator } from "@playwright/test";

export const OVERLAY_MARK = "data-parity-overlay";

export async function hideOverlays(target: ElementHandle<Element>): Promise<string[]> {
  return target.evaluate((element, mark) => {
    if (!document.getElementById(mark)) {
      const style = document.createElement("style");
      style.id = mark;
      style.textContent = `[${mark}], [${mark}] * { visibility: hidden !important; }`;
      document.head.append(style);
    }
    const overlays = [...document.body.querySelectorAll("*")].filter((other) => {
      if (element.contains(other) || other.contains(element)) return false;
      const position = getComputedStyle(other).position;
      return position === "sticky" || position === "fixed";
    });
    for (const overlay of overlays) overlay.setAttribute(mark, "");
    return overlays.map((overlay) => overlay.id || overlay.tagName.toLowerCase());
  }, OVERLAY_MARK);
}

export async function showOverlays(target: ElementHandle<Element>): Promise<void> {
  await target.evaluate((_, mark) => {
    for (const overlay of document.querySelectorAll(`[${mark}]`)) overlay.removeAttribute(mark);
  }, OVERLAY_MARK);
}

export async function withoutOverlays<T>(target: ElementHandle<Element>, capture: () => Promise<T>): Promise<T> {
  await hideOverlays(target);
  try {
    return await capture();
  } finally {
    await showOverlays(target);
  }
}

export async function overlayFreeShot(target: Locator, timeout: number): Promise<Buffer | null> {
  const element = await target.elementHandle({ timeout }).catch(() => null);
  if (!element) return null;
  return withoutOverlays(element, () => target.screenshot({ animations: "disabled", timeout }).catch(() => null));
}
