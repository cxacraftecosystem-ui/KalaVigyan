import type { CraftPage, MastheadGi, PageClaim } from "@/lib/craftPageContract";
import type { Citation, SourceRef } from "@/lib/types";

export const LANDING_CRAFT_SLUG = "Kutch-Ajrakh";
export const LANDING_CRAFT_NAME = "Kutch Ajrakh";

export const LANDING_CLAIMS = {
  vat: "C086",
  demo: "C022"
} as const;

export type LandingSentence = { id: string; text: string; citations: Citation[] };
export type LandingContent = {
  craftPath: string | null;
  name: string;
  family: string | null;
  place: string | null;
  gi: LandingSentence | null;
  vat: LandingSentence | null;
  demo: LandingSentence | null;
  sources: SourceRef[];
};

export type TextPart = { text: string; italic: boolean };

export type ClaimIdOf = (key: string) => string;

const GI_WORDS: Record<MastheadGi["status"], string> = {
  REGISTERED: "Registered geographical indication",
  APPLIED: "Geographical indication applied for"
};

const DAY = /^(\d{4})-(\d{2})-(\d{2})$/;
const DAY_FORMAT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export function giDay(value: string): string {
  const parts = DAY.exec(value);
  if (!parts) return value.slice(0, 4);
  return DAY_FORMAT.format(new Date(Date.UTC(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]))));
}

export function giSentence(gi: MastheadGi | null): LandingSentence | null {
  if (!gi) return null;
  const text = gi.on ? `${GI_WORDS[gi.status]}, ${giDay(gi.on)}` : GI_WORDS[gi.status];
  return { id: "gi", text, citations: gi.citations };
}

function sentenceOf(claim: PageClaim | undefined): LandingSentence | null {
  if (!claim || claim.citations.length === 0) return null;
  return { id: claim.id, text: claim.text, citations: claim.citations };
}

function escapedTerm(term: string): string {
  return term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function italicParts(text: string, terms: readonly string[]): TextPart[] {
  if (terms.length === 0) return [{ text, italic: false }];
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}])(${terms.map(escapedTerm).join("|")})(?![\\p{L}\\p{N}])`, "gu");
  const parts: TextPart[] = [];
  let at = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > at) parts.push({ text: text.slice(at, start), italic: false });
    parts.push({ text: match[0], italic: true });
    at = start + match[0].length;
  }
  if (at < text.length) parts.push({ text: text.slice(at), italic: false });
  return parts;
}

export function sourcesInOrder(sentences: readonly (LandingSentence | null)[], sources: readonly SourceRef[]): SourceRef[] {
  const byId = new Map(sources.map((source) => [source.id, source]));
  const seen = new Set<string>();
  const ordered: SourceRef[] = [];
  for (const sentence of sentences) {
    for (const citation of sentence?.citations ?? []) {
      const source = byId.get(citation.sourceId);
      if (!source || seen.has(source.id)) continue;
      seen.add(source.id);
      ordered.push(source);
    }
  }
  return ordered;
}

function plainSource(source: SourceRef): SourceRef {
  return { id: source.id, kind: source.kind, title: source.title, authors: source.authors, year: source.year, doi: source.doi, url: source.url, publisher: source.publisher, licence: source.licence, attribution: source.attribution, reliability: source.reliability };
}

export function emptyLanding(): LandingContent {
  return { craftPath: null, name: LANDING_CRAFT_NAME, family: null, place: null, gi: null, vat: null, demo: null, sources: [] };
}

export function landingContent(page: CraftPage | null, claimIdOf: ClaimIdOf): LandingContent {
  if (!page) return emptyLanding();
  const claims = new Map(page.claims.map((claim) => [claim.id, claim]));
  const pick = (key: string) => sentenceOf(claims.get(claimIdOf(key)));
  const kicker = [page.masthead.kicker.family, page.masthead.kicker.kind].filter(Boolean).join(" · ");
  const content: LandingContent = {
    craftPath: page.craft.path,
    name: page.masthead.name,
    family: kicker || null,
    place: page.masthead.place,
    gi: giSentence(page.masthead.gi),
    vat: pick(LANDING_CLAIMS.vat),
    demo: pick(LANDING_CLAIMS.demo),
    sources: []
  };
  return { ...content, sources: sourcesInOrder([content.vat, content.gi, content.demo], page.sources).map(plainSource) };
}

export function sourceNumbers(sources: readonly SourceRef[]): Map<string, number> {
  return new Map(sources.map((source, index) => [source.id, index + 1]));
}
