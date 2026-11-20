export const DEFERRED_ATTRIBUTE = "data-kv-deferred";
export const SHELL_COMPLETE_EVENT = "kv-shell-complete";
export const KIT_READY_EVENT = "kv-kit-ready";
export const CITATION_SELECTOR = ".kcite";

export function shellWaiting(root: ParentNode): boolean {
  return root.querySelector(`[${DEFERRED_ATTRIBUTE}]`) !== null;
}

export function announce(target: EventTarget, name: string): void {
  target.dispatchEvent(new Event(name));
}

export function whenShellComplete(start: () => void, view: Window, root: ParentNode): () => void {
  if (!shellWaiting(root)) {
    start();
    return () => undefined;
  }
  const onComplete = () => start();
  view.addEventListener(SHELL_COMPLETE_EVENT, onComplete, { once: true });
  return () => view.removeEventListener(SHELL_COMPLETE_EVENT, onComplete);
}

export function heldCitation(view: Window, kitBound: () => boolean): { taken: () => HTMLElement | null; stop: () => void } {
  let held: HTMLElement | null = null;
  const onClick = (event: Event) => {
    const target = event.target as { closest?: (selector: string) => HTMLElement | null } | null;
    const button = typeof target?.closest === "function" ? target.closest(CITATION_SELECTOR) : null;
    if (!button || kitBound()) return;
    held = button;
  };
  view.addEventListener("click", onClick, true);
  return {
    taken: () => {
      const found = held;
      held = null;
      return found;
    },
    stop: () => view.removeEventListener("click", onClick, true)
  };
}
