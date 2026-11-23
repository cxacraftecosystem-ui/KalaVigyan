import type { ElementHandle, Locator } from "@playwright/test";

export const OVERLAY_MARK = "data-parity-overlay";

export type OverlayFreeShot = { image: Buffer | null; hidden: string[]; place: string };
export type HiddenOverlays = { hidden: string[]; place: string };

export async function hideOverlays(target: ElementHandle<Element>): Promise<HiddenOverlays> {
  return target.evaluate((element, mark) => {
    if (!document.getElementById(mark)) {
      const style = document.createElement("style");
      style.id = mark;
      style.textContent = `[${mark}], [${mark}] * { visibility: hidden !important; }`;
      document.head.append(style);
    }
    const box = element.getBoundingClientRect();
    const overlays = [...document.body.querySelectorAll("*")].filter((other) => {
      if (element.contains(other) || other.contains(element)) return false;
      const position = getComputedStyle(other).position;
      if (position !== "sticky" && position !== "fixed") return false;
      const rect = other.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && rect.left < box.right && rect.right > box.left && rect.top < box.bottom && rect.bottom > box.top;
    });
    for (const overlay of overlays) overlay.setAttribute(mark, "");
    const named = (overlay: Element) => {
      const rect = overlay.getBoundingClientRect();
      const classes = typeof overlay.className === "string" ? overlay.className.trim().split(/\s+/).filter(Boolean).slice(0, 2).join(".") : "";
      return `${overlay.id || overlay.tagName.toLowerCase()}${classes ? `.${classes}` : ""} ${getComputedStyle(overlay).position} ${rect.top.toFixed(2)}+${rect.height.toFixed(2)}`;
    };
    return { hidden: overlays.map(named), place: `scroll ${window.scrollY.toFixed(2)} top ${box.top.toFixed(3)} height ${box.height.toFixed(2)}` };
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

export async function overlayFreeShot(target: Locator, timeout: number): Promise<OverlayFreeShot> {
  await target.scrollIntoViewIfNeeded({ timeout }).catch(() => undefined);
  const element = await target.elementHandle({ timeout }).catch(() => null);
  if (!element) return { image: null, hidden: [], place: "" };
  const { hidden, place } = await hideOverlays(element);
  try {
    return { image: await target.screenshot({ animations: "disabled", timeout }).catch(() => null), hidden, place };
  } finally {
    await showOverlays(element);
  }
}
