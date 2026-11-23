import { craftLinkShape, sourceRefShape, type CraftLink } from "@/lib/answerShapes";
import { TERM_KEY } from "@/lib/explainerBlockBase";
import { conceptCraftShape, conceptNodeShape, type ConceptCraft, type ConceptNode } from "@/lib/explainerLearning";
import { count, list, object, oneOf, positive, text, type Shape } from "@/lib/shape";
import type { SourceRef } from "@/lib/types";

export const CRAFT_SHARED_SCIENCE_PATH = (slug: string) => `/crafts/${encodeURIComponent(slug)}/shared-science`;
export const SHARED_CONCEPT_PATH = (termKey: string, craft?: string) =>
  `/shared-science/${encodeURIComponent(termKey)}${craft ? `?craft=${encodeURIComponent(craft)}` : ""}`;
export const SHARED_CONCEPT_CRAFTS_PATH = (termKey: string, craft: string | null, offset: number) =>
  `/shared-science/${encodeURIComponent(termKey)}/crafts?${craft ? `craft=${encodeURIComponent(craft)}&` : ""}offset=${offset}`;

export type SharedScience = { schemaVersion: 1; craft: CraftLink; nodes: ConceptNode[]; sources: SourceRef[] };
export type SharedConcept = { schemaVersion: 1; node: ConceptNode; sources: SourceRef[] };
export type ConceptCraftsPage = { schemaVersion: 1; termKey: string; label: string; craftCount: number; offset: number; crafts: ConceptCraft[]; sources: SourceRef[] };

export const sharedScienceShape: Shape<SharedScience> = object<SharedScience>({
  schemaVersion: oneOf([1] as const),
  craft: craftLinkShape,
  nodes: list(conceptNodeShape),
  sources: list(sourceRefShape)
});

export const sharedConceptShape: Shape<SharedConcept> = object<SharedConcept>({
  schemaVersion: oneOf([1] as const),
  node: conceptNodeShape,
  sources: list(sourceRefShape)
});

export const conceptCraftsPageShape: Shape<ConceptCraftsPage> = object<ConceptCraftsPage>({
  schemaVersion: oneOf([1] as const),
  termKey: TERM_KEY,
  label: text,
  craftCount: positive,
  offset: count,
  crafts: list(conceptCraftShape, 1),
  sources: list(sourceRefShape)
});
