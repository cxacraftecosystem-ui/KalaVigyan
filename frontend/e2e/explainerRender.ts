import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CitationProvider, type CitationLookup } from "@/components/answer/CitationContext";
import { ExplainerReadingProvider } from "@/components/answer/ExplainerReading";
import { AuthProvider } from "@/components/AuthProvider";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ENGLISH } from "@/lib/answerLanguages";

export const NO_CITATIONS: CitationLookup = { numbers: new Map(), sourcesById: new Map() };

export function withReading(child: ReactElement, lookup: CitationLookup = NO_CITATIONS): string {
  const reading = { language: ENGLISH, original: false, hiddenTerms: new Set<string>(), onTerm: () => undefined, listen: null };
  return renderToStaticMarkup(createElement(ExplainerReadingProvider, { value: reading }, createElement(CitationProvider, { value: lookup }, child)));
}

export function withApp(child: ReactElement, lookup: CitationLookup = NO_CITATIONS): string {
  return withReading(createElement(AuthProvider, null, createElement(ThemeProvider, null, child)), lookup);
}

export function attribute(html: string, testId: string, name: string): string[] {
  return [...html.matchAll(new RegExp(`<[^>]*data-testid="${testId}"[^>]*>`, "g"))].map((tag) => new RegExp(`${name}="([^"]*)"`).exec(tag[0])?.[1] ?? "");
}

export function gridTracks(html: string): string[] {
  return [...html.matchAll(/grid-cols-\[([^\]]+)\]/g)].flatMap((found) => found[1].split("_"));
}

export const SHRINKABLE_TRACK = /^(minmax\(0,|repeat\(\d+,minmax\(0,)/;
export const FIXED_WIDE_WIDTH = /\b(min-)?w-\[\d{3,}px\]/;

const ENTITIES: Record<string, string> = { "&#x27;": "'", "&quot;": '"', "&lt;": "<", "&gt;": ">", "&amp;": "&" };

export function shownText(html: string): string {
  return html.replace(/&(#x27|quot|lt|gt|amp);/g, (entity) => ENTITIES[entity]);
}
