import { useEffect, type RefObject } from "react";

export const REST_AFTER_LOAD_MS = 5000;
export const REST_TRIGGERS = ["pointerdown", "keydown", "touchstart", "wheel", "scroll"] as const;

export function hashTargetMissing(hash: string, root: Document): boolean {
  const id = decodeURIComponent(hash.replace(/^#/, ""));
  return id !== "" && root.getElementById(id) === null;
}

function afterLoad(view: Window, root: Document, start: () => void): () => void {
  let timer = 0;
  const wait = () => {
    timer = view.setTimeout(start, REST_AFTER_LOAD_MS);
  };
  if (root.readyState === "complete") wait();
  else view.addEventListener("load", wait, { once: true });
  return () => {
    view.removeEventListener("load", wait);
    view.clearTimeout(timer);
  };
}

function inView(holder: Element | null, start: () => void): () => void {
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
    const stops: (() => void)[] = [];
    const go = () => {
      if (started) return;
      started = true;
      stops.forEach((stop) => stop());
      start();
    };
    for (const name of REST_TRIGGERS) {
      window.addEventListener(name, go, { passive: true });
      stops.push(() => window.removeEventListener(name, go));
    }
    stops.push(inView(holder.current, go), afterLoad(window, document, go));
    if (hashTargetMissing(window.location.hash, document)) go();
    return () => stops.forEach((stop) => stop());
  }, [holder, start]);
}
