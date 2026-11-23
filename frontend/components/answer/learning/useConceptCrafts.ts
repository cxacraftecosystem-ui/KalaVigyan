"use client";

import { useCallback, useMemo, useState } from "react";

import { joinedCrafts, LIST_CRAFTS_START, nodeCraftCount, restOfCrafts, shownCrafts } from "@/lib/conceptGraph";
import type { ConceptCraft, ConceptNode } from "@/lib/explainerLearning";
import { fetchConceptCrafts } from "@/lib/learningApi";
import type { SourceRef } from "@/lib/types";

export type ConceptCraftsPhase = "idle" | "reading" | "failed";

export type ConceptCraftsView = {
  shown: ConceptCraft[];
  total: number;
  all: boolean;
  phase: ConceptCraftsPhase;
  expandable: boolean;
  sources: SourceRef[];
  showAll: () => void;
};

type CraftsState = { more: ConceptCraft[]; sources: SourceRef[]; read: boolean; all: boolean; phase: ConceptCraftsPhase };

const FIRST: CraftsState = { more: [], sources: [], read: false, all: false, phase: "idle" };

export function useConceptCrafts(node: ConceptNode, focus: string | null): ConceptCraftsView {
  const [state, setState] = useState<CraftsState>(FIRST);
  const total = nodeCraftCount(node);
  const unread = !state.read && total > node.crafts.length;
  const showAll = useCallback(() => {
    if (state.phase === "reading") return;
    if (!unread) {
      setState((now) => ({ ...now, all: true }));
      return;
    }
    setState((now) => ({ ...now, phase: "reading" }));
    restOfCrafts(node, (offset) => fetchConceptCrafts(node.termKey, focus, offset)).then(
      (rest) => setState({ more: rest.crafts, sources: rest.sources, read: true, all: true, phase: "idle" }),
      (cause: unknown) => {
        console.error(cause);
        setState((now) => ({ ...now, phase: "failed" }));
      }
    );
  }, [focus, node, state.phase, unread]);
  const crafts = useMemo(() => joinedCrafts(node.crafts, state.more), [node.crafts, state.more]);
  return { shown: shownCrafts(crafts, state.all), total, all: state.all, phase: state.phase, expandable: total > LIST_CRAFTS_START, sources: state.sources, showAll };
}
