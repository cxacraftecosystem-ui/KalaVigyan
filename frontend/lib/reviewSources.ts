import { integer, list, nullable, object, optional, text, type Shape } from "@/lib/shape";

export type SourceQuote = { text: string; locator: string | null };
export type SuppliedProvenance = { suppliedSourceId: string; access: string; accessedOn: string; grade: string; confirmedBy: string | null; textSha256: string; characters: number };
export type FactSource = { title: string; url: string | null; licence: string | null; reliability: string; quotes: SourceQuote[]; supplied?: SuppliedProvenance };

export const sourceShape: Shape<FactSource> = object<FactSource>({
  title: text,
  url: nullable(text),
  licence: nullable(text),
  reliability: text,
  quotes: list(object<SourceQuote>({ text, locator: nullable(text) })),
  supplied: optional(
    object<SuppliedProvenance>({ suppliedSourceId: text, access: text, accessedOn: text, grade: text, confirmedBy: nullable(text), textSha256: text, characters: integer })
  )
});
