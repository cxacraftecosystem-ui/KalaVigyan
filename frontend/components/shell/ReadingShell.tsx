"use client";

import type { ReactElement, ReactNode } from "react";

import { useAuth } from "@/components/AuthProvider";
import { DynamicIslandNav } from "@/components/DynamicIslandNav";
import { ReadingBar } from "@/components/nav/ReadingBar";
import { AccountGate } from "@/components/shell/AccountGate";
import { ShellFrame } from "@/components/shell/ShellFrame";
import type { User } from "@/lib/types";

export type ReadingFrameState = { user: User | null; loading: boolean; onRetry: (() => void) | null };

export function readingFrame({ user, loading, onRetry }: ReadingFrameState, children: ReactNode): ReactElement {
  return (
    <AccountGate user={user}>
      <ShellFrame nav={user ? <DynamicIslandNav /> : <ReadingBar signIn={!loading} />} onRetry={onRetry}>
        {children}
      </ShellFrame>
    </AccountGate>
  );
}

export function ReadingShell({ children }: { children: ReactNode }) {
  const { user, loading, reach, retryMe } = useAuth();
  return readingFrame({ user, loading, onRetry: reach === "retrying" ? retryMe : null }, children);
}
