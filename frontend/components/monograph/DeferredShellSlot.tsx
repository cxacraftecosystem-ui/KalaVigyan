"use client";

import { useCallback, useEffect, useRef, useState, type ComponentType } from "react";

import { announce, SHELL_COMPLETE_EVENT } from "@/components/monograph/kitGate";
import { hashTargetMissing, useShellTrigger } from "@/components/monograph/useShellTrigger";
import { checkedDocumentRest, checkedShellRest, type DocumentRest, type RestPart, type ShellRest } from "@/lib/monographRenderShell";

export const REST_UNREAD = "The rest of this monograph could not be read. Reload the page to try again.";

type RestView<T> = ComponentType<{ part: T; jump: string | null }>;
type ReadRest = { part: "document"; View: RestView<DocumentRest>; rest: DocumentRest } | { part: "shell"; View: RestView<ShellRest>; rest: ShellRest };
type Shown = ReadRest & { jump: string | null };

async function readBody(src: string): Promise<unknown> {
  const response = await fetch(src);
  if (!response.ok) throw new Error(`${REST_UNREAD} (${response.status})`);
  return response.json();
}

async function readRest(src: string, version: number, part: RestPart): Promise<ReadRest> {
  if (part === "document") {
    const [loaded, body] = await Promise.all([import("@/components/monograph/DeferredDocument"), readBody(src)]);
    return { part, View: loaded.DeferredDocument, rest: checkedDocumentRest(body, version) };
  }
  const [loaded, body] = await Promise.all([import("@/components/monograph/DeferredShell"), readBody(src)]);
  return { part, View: loaded.DeferredShell, rest: checkedShellRest(body, version) };
}

function missingTarget(): string | null {
  return hashTargetMissing(window.location.hash, document) ? decodeURIComponent(window.location.hash.slice(1)) : null;
}

function ShownRest({ shown }: { shown: Shown }) {
  if (shown.part === "document") return <shown.View part={shown.rest} jump={shown.jump} />;
  return <shown.View part={shown.rest} jump={shown.jump} />;
}

function Unread() {
  useEffect(() => announce(window, SHELL_COMPLETE_EVENT), []);
  return (
    <p role="status" className="kv-wrap font-ui text-ui text-ink-2">
      {REST_UNREAD}
    </p>
  );
}

export function DeferredShellSlot({ src, version, part = "shell" }: { src: string; version: number; part?: RestPart }) {
  const holder = useRef<HTMLDivElement | null>(null);
  const [shown, setShown] = useState<Shown | null>(null);
  const [failed, setFailed] = useState(false);
  const start = useCallback(() => {
    readRest(src, version, part).then(
      (read) => setShown({ ...read, jump: missingTarget() }),
      () => setFailed(true)
    );
  }, [src, version, part]);
  useShellTrigger(holder, start);
  if (shown) return <ShownRest shown={shown} />;
  if (failed) return <Unread />;
  return <div ref={holder} className="min-h-[300vh]" aria-busy="true" data-kv-deferred="" />;
}
