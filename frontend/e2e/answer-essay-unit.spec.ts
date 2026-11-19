import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { MediaCredit } from "@/components/answer/MediaPlate";

import { answerProvenance, essayDirection, essayScript, essaySections, essaySourceNumbers, creditParts, marginPicture, scriptLeading, sectionNotes, sentenceMark, shownQuestion, textScript } from "@/lib/answerEssay";
import { firingTitle, lostWaxTitle, mordantLabel, mordantTitle, signatureStepLabel } from "@/lib/answerSignature";
import type { ExplainerSentence, MediaRef } from "@/lib/explainerBlockBase";
import type { ExplainerBlock } from "@/lib/explainerContract";
import type { SectionView } from "@/lib/explainerState";
import type { Citation, SourceRef } from "@/lib/types";

const cite = (sourceId: string, evidence: Citation["evidence"] = "QUOTED"): Citation => ({ id: `c-${sourceId}`, claimId: `k-${sourceId}`, sourceId, quote: evidence === "QUOTED" ? "a quote" : null, locator: null, context: null, evidence, level: "VERIFIED" });
const said = (id: string, sources: string[], level: ExplainerSentence["level"] = "VERIFIED"): ExplainerSentence => ({ id, text: `Sentence ${id}.`, level, citations: sources.map((source) => cite(source)), terms: [] });
const source = (id: string, title: string, year: number | null, reliability: SourceRef["reliability"]): SourceRef => ({ id, kind: "PAPER", title, authors: [], year, doi: null, url: null, publisher: null, licence: null, attribution: null, reliability });
const asBlock = (value: unknown): ExplainerBlock => value as ExplainerBlock;
const section = (id: string, state: SectionView["state"], blocks: unknown[]): SectionView => ({ id, discipline: "CHEMISTRY", title: id, order: 1, state, searched: null, blocks: blocks.map(asBlock) });
const media = (id: string, author: string | null, licence: string | null, credit: string | null): MediaRef => ({
  id,
  display: "INLINE",
  provider: "commons",
  pageUrl: "https://commons.wikimedia.org/wiki/File:Ajrak.jpg",
  imageUrl: "https://upload.wikimedia.org/wikipedia/commons/a/ab/Ajrak.jpg",
  width: 1280,
  height: 960,
  title: "Ajrak",
  alt: "An ajrakh cloth",
  author,
  site: "Wikimedia Commons",
  credit,
  licence,
  licenceUrl: null,
  sourceId: null,
  retrievedAt: "2026-11-01T00:00:00Z"
});

test("the provenance names the sources and their grades in a spoken summary, never a pipeline count", () => {
  const grades = ["A", "B", "A", null, "C", "B", "A"] as const;
  const shown = answerProvenance(grades.map((grade) => ({ reliability: grade })));
  expect(shown.sources).toBe("Drawn from 7 sources");
  expect(shown.grades).toEqual([
    { grade: "A", count: 3 },
    { grade: "B", count: 2 },
    { grade: "C", count: 1 }
  ]);
  expect(shown.spoken).toBe("Reliability of the 7 sources: 3 graded A, 2 graded B and 1 graded C");
  expect(answerProvenance([{ reliability: null }])).toEqual({ sources: "Drawn from 1 source", grades: [], spoken: "" });
});

test("a sentence carries a mark only where it differs from the page's norm", () => {
  expect(sentenceMark(said("a", ["s1"], "HYPOTHESIS"))).toBe("hypothesis");
  expect(sentenceMark({ level: "PROVISIONAL", citations: [cite("s1", "INFERRED"), cite("s2", "INFERRED")] })).toBe("inferred");
  expect(sentenceMark({ level: "PROVISIONAL", citations: [cite("s1", "INFERRED"), cite("s2")] })).toBeNull();
  expect(sentenceMark(said("b", ["s1"]))).toBeNull();
});

test("a long question shows as a display line cut at a word, with the full wording kept", () => {
  expect(shownQuestion("How does indigo turn blue on Kutch Ajrakh cloth?")).toEqual({ shown: "How does indigo turn blue on Kutch Ajrakh cloth?", full: null });
  const long = `${"Why does the alum mordant printed in tamarind paste ".repeat(3)}hold the red?`;
  const shown = shownQuestion(long);
  expect(shown.full).toBe(long.trim());
  expect(shown.shown.endsWith("…")).toBe(true);
  expect(shown.shown.length).toBeLessThanOrEqual(81);
  expect(long.startsWith(shown.shown.slice(0, -1))).toBe(true);
  expect(shown.shown.slice(0, -1).endsWith(" ")).toBe(false);
});

test("an Arabic-script answer mirrors its region and takes its own script's face and leading", () => {
  const urdu = { code: "ur", script: "Arab", direction: "rtl" as const };
  expect(essayDirection(urdu, false)).toBe("rtl");
  expect(essayDirection(urdu, true)).toBe("ltr");
  expect(essayDirection({ direction: "ltr" }, false)).toBe("ltr");
  expect(essayScript(urdu)).toBe("Aran");
  expect(essayScript({ code: "sd", script: "Arab" })).toBe("Arab");
  expect(essayScript({ code: "hi", script: "Deva" })).toBe("Deva");
  expect(essayScript({ code: "en", script: "Latn" })).toBeNull();
  expect(textScript("ur", urdu)).toBe("Aran");
  expect(textScript("en", urdu)).toBeNull();
  expect([scriptLeading("Aran", "prose"), scriptLeading("Aran", "display"), scriptLeading(null, "prose")]).toEqual(["leading-[2.2]", "leading-[1.7]", null]);
});

test("the essay keeps sections that hold blocks and, only while it streams, the ones still being written", () => {
  const prose = { id: "s1.b1", kind: "prose", version: 1, reuse: null, sentences: [said("s1.b1.1", ["s1"])] };
  const sections = [section("s1", "READY", [prose]), section("s2", "EMPTY", []), section("s3", "WRITING", [])];
  expect(essaySections(sections, false).map((shown) => shown.id)).toEqual(["s1"]);
  expect(essaySections(sections, true).map((shown) => shown.id)).toEqual(["s1", "s3"]);
});

test("margin notes list a section's sources once each, in the order its sentences first cite them", () => {
  const prose = { id: "s1.b1", kind: "prose", version: 1, reuse: null, sentences: [said("s1.b1.1", ["s3", "s1"]), said("s1.b1.2", ["s1", "s2"])] };
  const numbers = new Map([
    ["s1", 1],
    ["s2", 2],
    ["s3", 3]
  ]);
  const sourcesById = new Map([source("s1", "GI Journal No. 188", 2023, "A"), source("s2", "Ajrakh", 2022, "B"), source("s3", "Natural Colorants", null, "A")].map((entry): [string, SourceRef] => [entry.id, entry]));
  expect(sectionNotes([asBlock(prose)], numbers, sourcesById)).toEqual([
    { number: 1, title: "GI Journal No. 188", year: 2023, anchorId: "say-s1.b1.1" },
    { number: 3, title: "Natural Colorants", year: null, anchorId: "say-s1.b1.1" },
    { number: 2, title: "Ajrakh", year: 2022, anchorId: "say-s1.b1.2" }
  ]);
});

test("a picture's credit puts the author and licence first, or the holder's own credit", () => {
  expect(creditParts(media("m1", "SMarndi", "CC BY-SA 4.0", null))).toEqual({ author: "SMarndi", licence: "CC BY-SA 4.0", site: "Wikimedia Commons" });
  expect(creditParts(media("m2", null, null, "© Victoria and Albert Museum, London"))).toEqual({ holder: "© Victoria and Albert Museum, London" });
  const credit = (shown: MediaRef) => renderToStaticMarkup(createElement(MediaCredit, { media: shown }));
  const licensed = credit({ ...media("m1", "SMarndi", "CC BY-SA 4.0", null), licenceUrl: "https://creativecommons.org/licenses/by-sa/4.0" });
  expect(licensed.replace(/<[^>]+>/g, "").replace(" (opens in a new tab)", "")).toBe("Photo: SMarndi, CC BY-SA 4.0, via Wikimedia Commons");
  expect(licensed).toContain('href="https://creativecommons.org/licenses/by-sa/4.0"');
  expect(credit(media("m3", null, null, null))).toBe("Via Wikimedia Commons");
});

test("a section's lone picture becomes its margin plate; a gallery stays in the column", () => {
  const one = { id: "s1.b2", kind: "images", version: 1, reuse: null, items: [{ media: media("m1", "A", "CC0", null), claimIds: [], relevance: "TEXT" }] };
  const two = { ...one, items: [...one.items, { media: media("m2", "B", "CC0", null), claimIds: [], relevance: "TEXT" }] };
  expect(marginPicture([asBlock(one)])?.blockId).toBe("s1.b2");
  expect(marginPicture([asBlock(two)])).toBeNull();
});

test("a ladder's reasons, tools, readings and cloth after are numbered after the sources already cited", () => {
  const stage = {
    stageId: "st1",
    ordinal: 1,
    name: "Dyeing",
    stageType: "DYE",
    level: "VERIFIED",
    sentences: [said("s1.b1.1", ["s1"])],
    materials: [],
    conditions: [],
    reactionIds: [],
    why: said("s1.b1.w", ["s4"]),
    tools: [{ toolId: "t1", name: "Vat", localNames: [], citations: [cite("s5")] }],
    after: { text: "green", colours: [], citations: [cite("s1"), cite("s6")] }
  };
  const ladder = { id: "s1.b1", kind: "process_ladder", version: 1, reuse: null, craft: { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" }, processId: "p1", stages: [stage] };
  const numbers = essaySourceNumbers(new Map([["s1", 1]]), [section("s1", "READY", [ladder])]);
  expect([...numbers.entries()]).toEqual([
    ["s1", 1],
    ["s4", 2],
    ["s5", 3],
    ["s6", 4]
  ]);
});

test("the signature figures describe what they draw in sentence case", () => {
  expect(mordantTitle({ dye: "madder", fibre: "cotton" })).toBe("Madder on cotton");
  expect(mordantLabel({ mordant: "alum", colour: "red" })).toBe("Alum gives red");
  expect(mordantLabel({ mordant: null, colour: "brown" })).toBe("Without a mordant, brown");
  expect(lostWaxTitle({ metal: "brass" })).toBe("Casting brass by lost wax");
  expect(firingTitle({ body: "terracotta" })).toBe("Firing terracotta");
  expect(signatureStepLabel("OXIDISING", "red")).toBe("Oxidising fire, red");
  expect(signatureStepLabel("BREAK_OUT")).toBe("Mould broken");
});
