"use client";

import { TriangleAlert } from "lucide-react";

import { ErrorBrand, ErrorPanel } from "@/components/ErrorPanel";
import { Button } from "@/components/ui/button";
import { errorCopy } from "@/lib/errorKind";

const COPY = errorCopy("global");

export function GlobalErrorView({ reference }: { reference?: string | null }) {
  return (
    <main id="main-content" className="kv-shell-main kv-shell-wrap min-h-dvh">
      <ErrorBrand />
      <ErrorPanel
        screen="global"
        tone="alert"
        icon={<TriangleAlert className="h-5 w-5" aria-hidden />}
        title={COPY.title}
        line={COPY.line}
        reference={reference}
      >
        <Button type="button" variant="primary" onClick={() => window.location.reload()}>
          Reload
        </Button>
      </ErrorPanel>
    </main>
  );
}
