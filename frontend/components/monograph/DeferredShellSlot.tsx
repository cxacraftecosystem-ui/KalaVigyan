"use client";

import { useCallback, useEffect, useRef, useState, type ComponentType } from "react";

import { announce, SHELL_COMPLETE_EVENT } from "@/components/monograph/kitGate";
import { hashTargetMissing, useShellTrigger } from "@/components/monograph/useShellTrigger";
import { checkedShellRest, type ShellRest } from "@/lib/monographRenderShell";

export const REST_UNREAD = "The rest of this monograph could not be read. Reload the page to try again.";

type RestView = ComponentType<{ part: ShellRest; jump: string | null }>;
type Shown = { View: RestView; part: ShellRest; jump: string | null };

async function readRest(src: string, version: number): Promise<{ View: RestView; part: ShellRest }> {
  const [loaded, response] = await Promise.all([import("@/components/monograph/DeferredShell"), fetch(src)]);
  if (!response.ok) throw new Error(`${REST_UNREAD} (${response.status})`);
  return { View: loaded.DeferredShell, part: checkedShellRest(await response.json(), version) };
}

function Unread() {
  useEffect(() => announce(window, SHELL_COMPLETE_EVENT), []);
  return (
    <p role="status" className="kv-wrap font-ui text-ui text-ink-2">
      {REST_UNREAD}
    </p>
  );
}

export function DeferredShellSlot({ src, version }: { src: string; version: number }) {
  const holder = useRef<HTMLDivElement | null>(null);
  const [shown, setShown] = useState<Shown | null>(null);
  const [failed, setFailed] = useState(false);
  const start = useCallback(() => {
    const jump = hashTargetMissing(window.location.hash, document) ? window.location.hash.slice(1) : null;
    readRest(src, version).then(
      (read) => setShown({ ...read, jump }),
      () => setFailed(true)
    );
  }, [src, version]);
  useShellTrigger(holder, start);
  if (shown) return <shown.View part={shown.part} jump={shown.jump} />;
  if (failed) return <Unread />;
  return <div ref={holder} className="min-h-[300vh]" aria-busy="true" data-kv-deferred="" />;
}
