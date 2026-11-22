"use client";

import { useRemote } from "@/components/hooks/useRemote";
import { fetchMapLayers } from "@/lib/mapLayers";

export function useOutlineCaption(): string | null {
  return useRemote(fetchMapLayers).data?.outlineCaption ?? null;
}
