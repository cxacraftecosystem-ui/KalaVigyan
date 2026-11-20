import { clusterName, shownNumbers } from "@/lib/citationCluster";
import type { MonographDocument } from "@/lib/monographDocument";
import { parseMonographDocument } from "@/lib/monographDocumentShape";
import { escapeAttribute } from "@/lib/monographRender";

const CITATION_CLASS = 'class="kcite"';
const CITATION_BUTTON = /(<button class="kcite"[^>]*? aria-label=")[^"]*("[^>]*>)([^<]*)(<\/button>)/g;

export function namedCitations(html: string): string {
  if (!html.includes(CITATION_CLASS)) return html;
  return html.replace(CITATION_BUTTON, (_, open: string, close: string, shown: string, end: string) => `${open}${escapeAttribute(clusterName(shownNumbers(shown)))}${close}${shown}${end}`);
}

export function withNamedStrings<T>(value: T): T {
  if (typeof value === "string") return namedCitations(value) as T;
  if (Array.isArray(value)) return value.map((item) => withNamedStrings(item)) as T;
  if (value === null || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, withNamedStrings(item)])) as T;
}

export function withNamedCitations(document: MonographDocument): MonographDocument {
  return {
    ...document,
    shell: document.shell === null ? null : namedCitations(document.shell),
    fragments: withNamedStrings(document.fragments),
    specs: withNamedStrings(document.specs),
    content: { ...document.content, data: withNamedStrings(document.content.data) }
  };
}

export function parseNamedDocument(raw: unknown): MonographDocument {
  return withNamedCitations(parseMonographDocument(raw));
}
