"use client";

import { useEffect } from "react";

import { announce, heldCitation, KIT_READY_EVENT, whenShellComplete } from "@/components/monograph/kitGate";
import { MONOGRAPH_KIT_JS } from "@/lib/monographDocument";

export const KIT_SCRIPT_MARK = "data-monograph-kit";
export const KIT_IDLE_TIMEOUT_MS = 2000;

type KitWindow = Window & { KV?: unknown };

export function kitAlreadyBound(view: KitWindow): boolean {
  return view.KV !== undefined;
}

function appendKit(onReady: () => void): void {
  const script = document.createElement("script");
  script.src = MONOGRAPH_KIT_JS;
  script.async = false;
  script.setAttribute(KIT_SCRIPT_MARK, "");
  script.addEventListener("load", onReady, { once: true });
  document.body.appendChild(script);
}

function afterLoadIdle(start: () => void): () => void {
  let idle = 0;
  const later = () => {
    idle = typeof window.requestIdleCallback === "function" ? window.requestIdleCallback(start, { timeout: KIT_IDLE_TIMEOUT_MS }) : window.setTimeout(start, 0);
  };
  if (document.readyState === "complete") later();
  else window.addEventListener("load", later, { once: true });
  return () => {
    window.removeEventListener("load", later);
    if (typeof window.cancelIdleCallback === "function") window.cancelIdleCallback(idle);
    window.clearTimeout(idle);
  };
}

export function KitScript() {
  useEffect(() => {
    if (kitAlreadyBound(window)) {
      window.location.reload();
      return;
    }
    if (document.querySelector(`script[${KIT_SCRIPT_MARK}]`)) return;
    const held = heldCitation(window, () => kitAlreadyBound(window));
    const ready = () => {
      held.stop();
      held.taken()?.click();
      announce(window, KIT_READY_EVENT);
    };
    let stopIdle: () => void = () => undefined;
    const stopShell = whenShellComplete(
      () => {
        stopIdle = afterLoadIdle(() => appendKit(ready));
      },
      window,
      document
    );
    return () => {
      held.stop();
      stopShell();
      stopIdle();
    };
  }, []);
  return null;
}
