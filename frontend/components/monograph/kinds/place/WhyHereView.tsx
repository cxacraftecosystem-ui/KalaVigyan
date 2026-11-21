"use client";

import { useMemo } from "react";

import { GroundFigure } from "@/components/map/place-context/GroundFigure";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { parseWhyHereSpec, type GroundNote } from "@/lib/placeGround";

export function heldNotes(notes: readonly GroundNote[], unitRefs: readonly string[]): GroundNote[] {
  const held = new Set(unitRefs);
  return notes.filter((note) => held.has(note.unit));
}

export function WhyHereView({ spec, unitRefs, renderUnit }: ComponentViewProps) {
  const parsed = useMemo(() => parseWhyHereSpec(spec), [spec]);
  const notes = useMemo(() => (parsed ? heldNotes(parsed.notes, unitRefs) : []), [parsed, unitRefs]);
  if (!parsed) return null;
  return <GroundFigure ground={parsed.ground} notes={notes} renderUnit={renderUnit} />;
}
