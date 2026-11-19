"use client";

import type { ReactNode } from "react";

import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button, type ButtonProps } from "@/components/ui/button";

export function RowActions({ children }: { children: ReactNode }) {
  return (
    <ActionGroup align="end" inline>
      {children}
    </ActionGroup>
  );
}

export function RowButton({ danger = false, ...props }: Omit<ButtonProps, "variant" | "size"> & { danger?: boolean }) {
  return <Button {...props} variant={danger ? "danger" : "quiet"} size="sm" data-danger={danger ? "" : undefined} />;
}
