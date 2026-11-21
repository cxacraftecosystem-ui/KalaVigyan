import { answerSentenceShape, citationShape, HTTPS_URL, INSTANT, UUID } from "@/lib/answerShapes";
import { boolean, integer, list, matching, nullable, object, oneOf, optional, ShapeError, text, type Shape } from "@/lib/shape";
import type { AnswerSentence, Citation } from "@/lib/types";

export const DISCIPLINES = [
  "OVERVIEW",
  "PROCESS",
  "CHEMISTRY",
  "PHYSICS",
  "MATERIALS",
  "GEOGRAPHY",
  "GEOLOGY",
  "CLIMATE",
  "ECOLOGY",
  "BOTANY",
  "HISTORY",
  "ECONOMICS",
  "DESIGN",
  "HEALTH",
  "SOCIETY",
  "POLICY"
] as const;
export const MEDIA_DISPLAYS = ["INLINE", "LINK_CARD"] as const;
export const IMAGE_RELEVANCE = ["TEXT", "VISION"] as const;

export type Discipline = (typeof DISCIPLINES)[number];
export type TermSpan = { text: string; termKey: string };
export type ExplainerSentence = AnswerSentence & { terms: TermSpan[]; sourcesDiffer?: boolean };
export type ReuseMarker = { pieceId: string; storedAt: string };
export type LadderCondition = { label: string; stated: string; citations: Citation[] };
export type BlockEnvelope<K extends string> = { id: string; kind: K; version: 1; reuse: ReuseMarker | null };
export type MediaRef = {
  id: string;
  display: (typeof MEDIA_DISPLAYS)[number];
  provider: string;
  pageUrl: string;
  imageUrl: string;
  width: number | null;
  height: number | null;
  title: string;
  alt: string;
  author: string | null;
  site: string;
  credit: string | null;
  licence: string | null;
  licenceUrl: string | null;
  sourceId: string | null;
  retrievedAt: string;
};

export const BLOCK_ID = matching(/^[a-z0-9]+(?:[.-][a-z0-9]+)*$/, "a block id");
export const TERM_KEY = matching(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "a term key");
export const WIKIDATA_ID = matching(/^Q[1-9]\d*$/, "a Wikidata id");

export const termSpanShape: Shape<TermSpan> = object<TermSpan>({ text, termKey: TERM_KEY });
export const ladderConditionShape: Shape<LadderCondition> = object<LadderCondition>({ label: text, stated: text, citations: list(citationShape, 1) });

export const mediaRefShape: Shape<MediaRef> = object<MediaRef>({
  id: UUID,
  display: oneOf(MEDIA_DISPLAYS),
  provider: matching(/^[a-z][a-z0-9_]{1,39}$/, "a provider name"),
  pageUrl: HTTPS_URL,
  imageUrl: HTTPS_URL,
  width: nullable(integer),
  height: nullable(integer),
  title: text,
  alt: text,
  author: nullable(text),
  site: text,
  credit: nullable(text),
  licence: nullable(text),
  licenceUrl: nullable(HTTPS_URL),
  sourceId: nullable(text),
  retrievedAt: INSTANT
});

export const explainerSentenceShape: Shape<ExplainerSentence> = {
  expected: "a cited sentence with its marked terms",
  parse(value, path) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new ShapeError(path, "an object");
    const { terms, sourcesDiffer, ...sentence } = value as Record<string, unknown>;
    const differs = optional(boolean).parse(sourcesDiffer, path ? `${path}.sourcesDiffer` : "sourcesDiffer");
    const parsed = { ...answerSentenceShape.parse(sentence, path), terms: list(termSpanShape).parse(terms, path ? `${path}.terms` : "terms") };
    return differs === undefined ? parsed : { ...parsed, sourcesDiffer: differs };
  }
};

export function envelope<K extends string>(kind: K) {
  return {
    id: BLOCK_ID,
    kind: oneOf([kind] as const) as Shape<K>,
    version: oneOf([1] as const),
    reuse: nullable(object<ReuseMarker>({ pieceId: UUID, storedAt: INSTANT }))
  };
}
