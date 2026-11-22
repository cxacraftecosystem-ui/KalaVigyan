import { boolean, integer, list, matching, nullable, object, oneOf, optional, text, type Shape } from "@/lib/shape";
import type { AnswerSentence, AnswerStatus, Citation, CraftRef, EvidenceLevel, SourceRef } from "@/lib/types";

export const SHOWN_LEVELS = ["VERIFIED", "REVIEWED", "PROVISIONAL", "HYPOTHESIS", "UNAVAILABLE"] as const;
export const STORED_LEVELS = ["VERIFIED", "REVIEWED", "PROVISIONAL", "HYPOTHESIS"] as const;

export type StoredLevel = (typeof STORED_LEVELS)[number];
export type CraftLink = CraftRef & { path: string };

export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export const UUID = matching(UUID_PATTERN, "a uuid");
export const INSTANT = matching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/, "an ISO instant");
export const HTTPS_URL = matching(/^https:\/\/\S+$/, "an https URL");

export const shownLevelShape: Shape<EvidenceLevel> = oneOf(SHOWN_LEVELS);
export const storedLevelShape: Shape<StoredLevel> = oneOf(STORED_LEVELS);

export const CRAFT_PATH = matching(/^\/crafts\/\S+$/, "a craft path");

export const craftLinkShape: Shape<CraftLink> = object<CraftLink>({
  slug: text,
  name: text,
  path: CRAFT_PATH
});

export const citationShape: Shape<Citation> = object<Citation>({
  id: text,
  claimId: text,
  sourceId: text,
  quote: nullable(text),
  locator: nullable(text),
  context: nullable(text),
  evidence: oneOf(["QUOTED", "INFERRED"] as const),
  level: shownLevelShape
});

export const sourceRefShape: Shape<SourceRef> = object<SourceRef>({
  id: text,
  kind: text,
  title: text,
  authors: list(text),
  year: nullable(integer),
  doi: nullable(text),
  url: nullable(HTTPS_URL),
  publisher: nullable(text),
  containerTitle: optional(text),
  licence: nullable(text),
  attribution: nullable(text),
  reliability: nullable(oneOf(["A", "B", "C", "D"] as const))
});

export const answerSentenceShape: Shape<AnswerSentence> = object<AnswerSentence>({
  id: text,
  text,
  level: shownLevelShape,
  citations: list(citationShape, 1),
  translated: optional(boolean),
  original: optional(text)
});

export const answerStatusShape: Shape<AnswerStatus> = object<AnswerStatus>({
  step: oneOf(["PLANNING", "SEARCHING_STORED", "RESEARCHING", "READING", "COMPOSING", "WRITING_BACK", "TRANSLATING"] as const),
  message: text
});
