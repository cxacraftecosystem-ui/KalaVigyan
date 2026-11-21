import { useEffect, type RefObject } from "react";

export const REST_AFTER_LOAD_MS = 5000;
export const REST_IDLE_WAIT_MS = 2000;
export const INTENT_TRIGGERS = ["pointerdown", "keydown", "touchstart"] as const;
export const SCROLL_TRIGGERS = ["wheel", "scroll"] as const;
export const REST_TRIGGERS = [...INTENT_TRIGGERS, ...SCROLL_TRIGGERS] as const;

type Stop = () => void;
type IdleView = Window & { requestIdleCallback?: (run: () => void, options: { timeout: number }) => number; cancelIdleCallback?: (handle: number) => void };

export function hashTargetMissing(hash: string, root: Document): boolean {
  const id = decodeURIComponent(hash.replace(/^#/, ""));
  return id !== "" && root.getElementById(id) === null;
}

export function afterLoad(view: Window, root: Document, then: () => void): Stop {
  if (root.readyState === "complete") {
    then();
    return () => undefined;
  }
  view.addEventListener("load", then, { once: true });
  return () => view.removeEventListener("load", then);
}

export function whenIdle(view: IdleView, start: () => void): Stop {
  if (typeof view.requestIdleCallback === "function") {
    const handle = view.requestIdleCallback(start, { timeout: REST_IDLE_WAIT_MS });
    return () => view.cancelIdleCallback?.(handle);
  }
  return () => undefined;
}

export function laterWhenIdle(view: IdleView, start: () => void): Stop {
  let idle: Stop = () => undefined;
  const timer = view.setTimeout(() => {
    if (typeof view.requestIdleCallback === "function") idle = whenIdle(view, start);
    else start();
  }, REST_AFTER_LOAD_MS);
  return () => {
    view.clearTimeout(timer);
    idle();
  };
}

function listened(view: Window, names: readonly string[], go: () => void): Stop[] {
  return names.map((name) => {
    view.addEventListener(name, go, { passive: true });
    return () => view.removeEventListener(name, go);
  });
}

function inView(holder: Element | null, start: () => void): Stop {
  if (!holder || typeof IntersectionObserver === "undefined") return () => undefined;
  const observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) start();
  });
  observer.observe(holder);
  return () => observer.disconnect();
}

export function useShellTrigger(holder: RefObject<Element | null>, start: () => void): void {
  useEffect(() => {
    let started = false;
    const stops: Stop[] = [];
    const go = () => {
      if (started) return;
      started = true;
      stops.forEach((stop) => stop());
      start();
    };
    const loaded = () => {
      if (!started) stops.push(...listened(window, SCROLL_TRIGGERS, go), inView(holder.current, go), laterWhenIdle(window, go));
    };
    stops.push(...listened(window, INTENT_TRIGGERS, go), afterLoad(window, document, loaded));
    if (hashTargetMissing(window.location.hash, document)) go();
    return () => stops.forEach((stop) => stop());
  }, [holder, start]);
}
