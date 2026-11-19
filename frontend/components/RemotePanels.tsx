"use client";

import type { ReactNode } from "react";
import { CircleAlert, RotateCw } from "lucide-react";

import type { Remote, RemoteFailure } from "@/components/hooks/useRemote";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";

export function LoadingPanel({ className, label = "Opening this page" }: { className?: string; label?: string }) {
  return <Skeleton shape="lede" label={label} className={cn("border-t border-rule pt-6", className)} />;
}

export function RetryPanel({ message, onRetry, className }: { message: string; onRetry: () => void; className?: string }) {
  return (
    <section role="alert" className={cn("grid justify-items-center gap-4 border-y border-rule px-4 py-10 text-center", className)}>
      <p className="flex max-w-[52ch] items-start gap-2 font-ui text-ui-lg text-ink-1">
        <CircleAlert className="mt-1 h-4 w-4 shrink-0 text-error" aria-hidden />
        <span className="min-w-0">{message}</span>
      </p>
      <Button type="button" variant="quiet" onClick={onRetry}>
        <RotateCw aria-hidden />
        Try again
      </Button>
    </section>
  );
}

export function RetryLine({ message, onRetry, className }: { message: string; onRetry: () => void; className?: string }) {
  return (
    <div role="alert" className={cn("flex flex-wrap items-center gap-3 font-ui text-ui text-ink-1", className)}>
      <span className="inline-flex min-w-0 items-start gap-2">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-error" aria-hidden />
        <span className="min-w-0">{message}</span>
      </span>
      <Button type="button" variant="quiet" size="sm" onClick={onRetry}>
        <RotateCw aria-hidden />
        Try again
      </Button>
    </div>
  );
}

export function RemoteView<T>({
  remote,
  failed,
  children
}: {
  remote: Remote<T>;
  failed: (failure: RemoteFailure) => string;
  children: (data: T) => ReactNode;
}) {
  if (remote.failure) return <RetryPanel message={failed(remote.failure)} onRetry={remote.retry} />;
  if (remote.data === null) return <LoadingPanel />;
  return <>{children(remote.data)}</>;
}
