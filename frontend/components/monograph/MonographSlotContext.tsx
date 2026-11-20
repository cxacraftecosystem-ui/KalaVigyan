"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { MonographSources } from "@/lib/monographRender";
import type { ComponentBundle } from "@/lib/monographRenderLayout";

export type MonographSlotValue = { sources: MonographSources; bundles: Readonly<Record<string, ComponentBundle>>; bare?: boolean };

const MonographSlotContext = createContext<MonographSlotValue | null>(null);

export function MonographSlotProvider({ value, children }: { value: MonographSlotValue; children: ReactNode }) {
  return <MonographSlotContext.Provider value={value}>{children}</MonographSlotContext.Provider>;
}

export function useMonographSlot(): MonographSlotValue {
  const value = useContext(MonographSlotContext);
  if (!value) throw new Error("A monograph component view is drawn inside its slot");
  return value;
}
