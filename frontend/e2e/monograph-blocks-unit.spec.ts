import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { prerender } from "react-dom/static";

import { AuthProvider } from "../components/AuthProvider";
import { ComponentSlot, slotDrawing } from "../components/monograph/ComponentSlot";
import { COMPONENT_VIEWS } from "../components/monograph/componentViews";
import { ANSWER_BLOCK_KIND, blockColumn, blockFrame, parseAnswerBlockSpec, sourceNumbers, type AnswerBlockSpec } from "../components/monograph/kinds/blocks/answerBlockSpec";
import { ThemeProvider } from "../components/ThemeProvider";
import type { PageBlock } from "../lib/craftChapters";
import type { MonographDocument, MonographSource } from "../lib/monographDocument";
import type { SourceRef } from "../lib/types";

import { rawPage } from "./craftPageFixture";
import { eagerModules } from "./moduleGraph";

const LABEL = "kutch-ajrakh/blocks/made-ladder";
const LADDER_STAGES = 14;
const REF_FIELDS = ["id", "kind", "title", "authors", "year", "doi", "url", "publisher", "licence", "attribution", "reliability"] as const;

async function provided(element: ReactElement): Promise<string> {
  const { prelude } = await prerender(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));
  return (await new Response(prelude).text()).replaceAll("<!-- -->", "");
}

function pageBlock(kind: string): PageBlock {
  for (const chapter of rawPage().chapters) for (const item of chapter.items) if (item.block && item.block.kind === kind) return item.block;
  throw new Error(`the golden page draws no ${kind}`);
}

function citedSources(node: unknown, found: Set<string> = new Set()): Set<string> {
  if (Array.isArray(node)) node.forEach((value) => citedSources(value, found));
  else if (node && typeof node === "object") {
    const record = node as Record<string, unknown>;
    if (typeof record.sourceId === "string" && typeof record.claimId === "string") found.add(record.sourceId);
    Object.values(record).forEach((value) => citedSources(value, found));
  }
  return found;
}

function refs(block: PageBlock): SourceRef[] {
  const cited = citedSources(block);
  return rawPage()
    .sources.filter((source) => cited.has(source.id))
    .map((source) => Object.fromEntries(REF_FIELDS.map((field) => [field, source[field]])) as SourceRef);
}

function spec(kind: string, figure: AnswerBlockSpec["figure"]): Record<string, unknown> {
  const block = pageBlock(kind);
  return { block, figure, sources: refs(block).map((ref, at) => ({ key: `g${at + 1}`, ref })) };
}

function source(number: number, ref: SourceRef): MonographSource {
  return { number, title: ref.title, fullTitle: null, publisher: ref.publisher, year: ref.year, grade: ref.reliability, url: ref.url, extra: null, dossierSourceId: null };
}

function documentWith(drawn: Record<string, unknown>): MonographDocument {
  const listed = (drawn.sources as { key: string; ref: SourceRef }[]).map((entry, at) => [entry.key, source(at + 3, entry.ref)] as const);
  return {
    schemaVersion: 1,
    subjectKind: "craft",
    subjectSlug: "Kutch-Ajrakh",
    language: "en",
    title: "Kutch Ajrakh",
    version: 3,
    content: {
      schemaVersion: 1,
      craftSlug: "Kutch-Ajrakh",
      sources: Object.fromEntries(listed),
      citations: {},
      citationClaims: {},
      data: {},
      units: {},
      components: [{ label: LABEL, chapter: "made", anchor: "#kutch-ajrakh--blocks--made-ladder", kind: ANSWER_BLOCK_KIND, title: "How Kutch Ajrakh is made, in 14 stages", description: "The stages.", field: "PROCESS", fields: [], subjects: ["craft:Kutch-Ajrakh"] }],
      layout: [{ chapter: "made", kind: "component", ref: LABEL, within: null }]
    },
    specs: { [LABEL]: drawn },
    fragments: {},
    shell: null,
    pageUrl: "https://kalavigyan.vercel.app/crafts/Kutch-Ajrakh"
  };
}

test("an answer block spec reads the page block, its figure head and every source it cites", () => {
  const parsed = parseAnswerBlockSpec(spec("process_ladder", { kind: "FIGURE", number: 1, title: "How Kutch Ajrakh is made, in 14 stages" }));
  expect(parsed).not.toBeNull();
  expect(parsed!.block.kind).toBe("process_ladder");
  expect(parsed!.sources.map((listed) => listed.key)).toEqual(refs(pageBlock("process_ladder")).map((_, at) => `g${at + 1}`));
  expect(parseAnswerBlockSpec({ ...spec("process_ladder", null), extra: true })).toBeNull();
  expect(parseAnswerBlockSpec({ ...spec("process_ladder", null), sources: [{ key: "s1", ref: refs(pageBlock("process_ladder"))[0] }] })).toBeNull();
});

test("a figure is framed by its kind: a signature figure by its own, a self-titled one by its numeral, any other by the figure frame", () => {
  const head = { kind: "FIGURE" as const, number: 2, title: "A figure" };
  const frames = (["process_ladder", "region_story", "mordant_bath"] as const).map((kind) => blockFrame(parseAnswerBlockSpec(spec(kind, head))!));
  expect(frames).toEqual(["titled", "numbered", "signature"]);
  expect(blockFrame(parseAnswerBlockSpec(spec("market_gi", null))!)).toBe("bare");
});

test("a map or a series spans the reading column and its margin, any other figure keeps to the reading column", () => {
  const columns = (["region_story", "climate_risk", "timeline_map", "process_ladder", "reaction_player", "market_gi"] as const).map((kind) => blockColumn(parseAnswerBlockSpec(spec(kind, null))!));
  expect(columns).toEqual(["wide", "wide", "wide", "main", "main", "main"]);
});

test("a block's numerals are the document's numbers for its listed sources", () => {
  const drawn = spec("process_ladder", null);
  const parsed = parseAnswerBlockSpec(drawn)!;
  const document = documentWith(drawn);
  const numbers = sourceNumbers(parsed, document.content.sources);
  expect([...numbers.values()]).toEqual(parsed.sources.map((_, at) => at + 3));
  expect([...numbers.keys()]).toEqual(parsed.sources.map((listed) => listed.ref.id));
});

test("a monograph loads the answer renderers only when it places an answer block", () => {
  const eager = eagerModules("@/components/monograph/componentViews");
  expect(eager.has("components/monograph/kinds/blocks/index.ts")).toBe(true);
  expect([...eager].filter((file) => file === "components/monograph/kinds/blocks/AnswerBlockView.tsx" || file === "components/answer/blockRenderers.ts")).toEqual([]);
});

test("the document draws an answer block natively, as the answer's own ladder inside its figure, its renderers loaded on demand", async () => {
  expect(COMPONENT_VIEWS[ANSWER_BLOCK_KIND]).toBeDefined();
  const document = documentWith(spec("process_ladder", { kind: "FIGURE", number: 1, title: "How Kutch Ajrakh is made, in 14 stages" }));
  expect(slotDrawing(document, LABEL)).toBe("view");
  const html = await provided(createElement(ComponentSlot, { document, label: LABEL }));
  expect(html).toContain('<div class="spread"><div class="main">');
  expect(html).toContain('data-testid="answer-block"');
  expect(html).toContain('data-block-kind="process_ladder"');
  expect(html).toContain("Fig. <b>1</b>");
  expect(html).toContain("How Kutch Ajrakh is made, in 14 stages");
  expect(html).toContain('data-testid="process-ladder"');
  expect(html.match(/<li[^>]*data-testid="ladder-stage"/g)).toHaveLength(LADDER_STAGES);
});
