import type { CraftPage, MastheadGi, PageClaim, PageStage } from "@/lib/craftPageContract";
import type { Citation, SourceRef } from "@/lib/types";

export const LANDING_CRAFT_SLUG = "Kutch-Ajrakh";
export const LANDING_CRAFT_NAME = "Kutch Ajrakh";
export const RIBBON_STAGE_COUNT = 11;

export const LANDING_CLAIMS = {
  vat: "C086",
  intro: "C004",
  black: "C078",
  red: "C093",
  whiteLime: "C072",
  whitePink: "C097",
  meanings: "C115",
  differ: "C114",
  demo: "C022"
} as const;

export const COLOUR_KEYS = ["blue", "black", "red", "white"] as const;
export type ColourKey = (typeof COLOUR_KEYS)[number];

export type LandingSentence = { id: string; text: string; citations: Citation[] };
export type LandingColour = { key: ColourKey; sentences: LandingSentence[] };
export type LandingStage = { order: number; label: string; local: boolean };
export type LandingContent = {
  craftPath: string | null;
  name: string;
  family: string | null;
  place: string | null;
  gi: LandingSentence | null;
  vat: LandingSentence | null;
  intro: LandingSentence | null;
  colours: LandingColour[];
  meanings: LandingSentence | null;
  differ: LandingSentence | null;
  demo: LandingSentence | null;
  stages: LandingStage[];
  botanical: string[];
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

export function rulerWord(name: string): string {
  return (name.trim().split(/\s+/)[0] ?? "").toLowerCase();
}

export function ribbonStages(stages: readonly PageStage[]): LandingStage[] {
  const ordered = stages.filter((stage): stage is PageStage & { order: number } => stage.order !== null).sort((a, b) => a.order - b.order);
  if (ordered.length !== RIBBON_STAGE_COUNT) return [];
  return ordered.map((stage) => {
    const local = stage.localName?.split(",")[0]?.trim() ?? "";
    return { order: stage.order, label: local || rulerWord(stage.name), local: local !== "" };
  });
}

export function botanicalNames(stages: readonly PageStage[]): string[] {
  const names = stages.flatMap((stage) => [...stage.materials, ...stage.tools]).flatMap((item) => (item.botanicalName?.trim() ? [item.botanicalName.trim()] : []));
  return [...new Set(names)].sort((a, b) => b.length - a.length);
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

function colours(pick: (key: string) => LandingSentence | null): LandingColour[] {
  const sentences: Record<ColourKey, (LandingSentence | null)[]> = {
    blue: [pick(LANDING_CLAIMS.vat)],
    black: [pick(LANDING_CLAIMS.black)],
    red: [pick(LANDING_CLAIMS.red)],
    white: [pick(LANDING_CLAIMS.whiteLime), pick(LANDING_CLAIMS.whitePink)]
  };
  return COLOUR_KEYS.map((key) => ({ key, sentences: sentences[key].filter((sentence): sentence is LandingSentence => sentence !== null) })).filter((colour) => colour.sentences.length > 0);
}

export function emptyLanding(): LandingContent {
  return { craftPath: null, name: LANDING_CRAFT_NAME, family: null, place: null, gi: null, vat: null, intro: null, colours: [], meanings: null, differ: null, demo: null, stages: [], botanical: [], sources: [] };
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
    intro: pick(LANDING_CLAIMS.intro),
    colours: colours(pick),
    meanings: pick(LANDING_CLAIMS.meanings),
    differ: pick(LANDING_CLAIMS.differ),
    demo: pick(LANDING_CLAIMS.demo),
    stages: ribbonStages(page.process.stages),
    botanical: botanicalNames(page.process.stages),
    sources: []
  };
  const order = [content.vat, content.gi, content.intro, ...content.colours.flatMap((colour) => colour.sentences), content.meanings, content.differ, content.demo];
  return { ...content, sources: sourcesInOrder(order, page.sources).map(plainSource) };
}

export function sourceNumbers(sources: readonly SourceRef[]): Map<string, number> {
  return new Map(sources.map((source, index) => [source.id, index + 1]));
}
