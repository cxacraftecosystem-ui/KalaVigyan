"use client";

import { useState } from "react";

import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const COPY_TEXTS = {
  address: { button: "Copy address", done: "Address copied.", failed: "The address could not be copied. Select it and copy it." },
  command: { button: "Copy command", done: "Command copied.", failed: "The command could not be copied. Select it and copy it." },
  configuration: { button: "Copy configuration", done: "Configuration copied.", failed: "The configuration could not be copied. Select it and copy it." },
  request: { button: "Copy request", done: "Request copied.", failed: "The request could not be copied. Select it and copy it." }
} as const;

export type CopyKind = keyof typeof COPY_TEXTS;

export function copyKindOf(code: string): CopyKind {
  if (code.trimStart().startsWith("{")) return "configuration";
  return /^https?:\/\//.test(code) ? "address" : "command";
}

export function CopyCode({ code, kind = copyKindOf(code), large = false }: { code: string; kind?: CopyKind; large?: boolean }) {
  const [status, setStatus] = useState("");
  const texts = COPY_TEXTS[kind];
  const block = kind === "configuration";
  const prose = kind === "request";

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setStatus(texts.done);
    } catch {
      setStatus(texts.failed);
    }
  }

  return (
    <div className="grid min-w-0 gap-2" data-testid={`copy-${kind}`}>
      <pre
        className={cn(
          "m-0 min-w-0 rounded-control border border-rule bg-sunk px-3 py-2 text-ink-1",
          prose ? "font-reading text-body-sm" : "font-code",
          prose ? null : large ? "text-ui-lg" : "text-label",
          block ? "overflow-x-auto whitespace-pre" : "whitespace-pre-wrap [overflow-wrap:anywhere]"
        )}
      >
        <code>{code}</code>
      </pre>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <ActionGroup inline align="start">
          <Button variant="quiet" size="sm" onClick={() => void copy()}>
            {texts.button}
          </Button>
        </ActionGroup>
        <p role="status" className="m-0 font-ui text-label text-ink-3">
          {status}
        </p>
      </div>
    </div>
  );
}
