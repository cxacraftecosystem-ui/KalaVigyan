import { expect, test } from "@playwright/test";

import { labelsOf } from "./production/appbarChecks";
import { segmentScreens } from "./production/capture";
import { CRAFT_TEMPLATES, drawnTemplate } from "./production/craftChecks";
import { NO_FAMILY_SCIENCE_NOTE, documentProblems, essayProblems, hubProblems, recordProblems } from "./production/pageGates";
import { DOCUMENT_ROOT, ESSAY_ROOT, HUB_ROOT, RAIL_LINKS, RECORD_ROOT, documentShape, essayShape, hubShape, recordShape, type DocumentShape, type RecordShape } from "./production/pageShapes";

const DOCUMENT: DocumentShape = { heading: "Kutch Ajrakh", chapters: ["The answer", "The cloth"], railTargets: ["answer", "cloth"], missingTargets: [], citedSentences: 12 };
const RECORD: RecordShape = { heading: "Kasuti Embroidery", facts: 4, start: "Start the research on Kasuti Embroidery", questions: 3, plate: true, rail: 0, citeThis: false };

test("a document passes with a heading, labelled chapters, a rail that reaches them and cited sentences", () => {
  expect(documentProblems(DOCUMENT)).toEqual([]);
  expect(documentProblems(null)).toEqual(["the page draws no document"]);
  expect(documentProblems({ heading: "", chapters: ["The answer", "", "The answer"], railTargets: ["answer", "sources"], missingTargets: ["sources"], citedSentences: 0 })).toEqual([
    "the document draws no h1",
    "1 of the 3 chapters carry no label",
    "the document draws a chapter twice: The answer",
    "the chapter rail links to chapters the page does not draw: sources",
    "the document draws no cited sentence"
  ]);
  expect(documentProblems({ ...DOCUMENT, chapters: [], railTargets: [] })).toEqual(["the document draws no chapter", "the chapter rail lists no chapter"]);
});

test("a craft without a monograph passes with its plate, its record and three questions that start research, and no rail or Cite this", () => {
  expect(recordProblems(RECORD)).toEqual([]);
  expect(recordProblems(null)).toEqual(["the page draws no craft record"]);
  expect(recordProblems({ ...RECORD, facts: 0, start: "Research Kasuti", questions: 2, plate: false, rail: 1, citeThis: true })).toEqual([
    "the craft record draws no typographic plate",
    "the craft record shows none of what the craft list records",
    'the research invitation reads "Research Kasuti"; it should read "Start the research on Kasuti Embroidery"',
    "the research invitation offers 2 questions; it should offer 3",
    "a craft without a monograph draws a chapter rail",
    "a craft without a monograph offers Cite this"
  ]);
});

test("a category hub is headed by its family on a plate and shelves its crafts; missing family science is a note", () => {
  const hub = { heading: "Textiles", plate: true, shelves: 5, plates: 25, chapters: 0 };
  expect(hubProblems(hub, "Textiles")).toEqual({ problems: [], notes: [NO_FAMILY_SCIENCE_NOTE] });
  expect(hubProblems({ ...hub, chapters: 4 }, "Textiles").notes).toEqual(["4 family science chapters"]);
  expect(hubProblems({ heading: "Metal", plate: false, shelves: 0, plates: 0, chapters: 0 }, "Textiles").problems).toEqual([
    'the hub is headed "Metal"; it should be headed Textiles',
    "the hub draws no plate ground behind its heading",
    "the hub draws no shelf of its sub-families",
    "the hub's shelves hold no craft"
  ]);
  expect(hubProblems(null, "Textiles").problems).toEqual(["the page draws no category hub"]);
});

test("an answer essay passes with its question, a cited lede and the two quiet actions", () => {
  const essay = { question: "Why does alum fix madder?", lede: 3, ledeCited: 3, actions: ["Save", "Cite this answer"] };
  expect(essayProblems(essay)).toEqual([]);
  expect(essayProblems({ ...essay, actions: ["Saved", "Cite this answer"] })).toEqual([]);
  expect(essayProblems({ question: "", lede: 3, ledeCited: 1, actions: ["Save"] })).toEqual([
    "the answer draws no question as its h1",
    "2 of the 3 lede sentences carry no citation",
    "the answer's actions are [Save]; they should be Save and Cite this answer"
  ]);
  expect(essayProblems({ ...essay, lede: 0, ledeCited: 0 })).toEqual(["the answer draws no lede"]);
});

test("a document is read from its chapters, its rail and its cited sentences", async ({ page }) => {
  await page.setContent(
    `<div class="kv-monograph"><nav aria-label="Chapters"><a href="#answer">The answer</a><a href="#made">How it is made</a><a href="#answer">The answer</a></nav>` +
      `<section class="kv-ch" id="answer" data-label="The answer"><h1>Kutch Ajrakh</h1><p><span data-src="a1">One.</span> <span data-src="a2">Two.</span></p></section>` +
      `<section class="kv-ch" id="cloth" data-label="The cloth"></section></div>`
  );
  expect(await page.evaluate(documentShape, { root: DOCUMENT_ROOT, rail: RAIL_LINKS })).toEqual({
    heading: "Kutch Ajrakh",
    chapters: ["The answer", "The cloth"],
    railTargets: ["answer", "made"],
    missingTargets: ["made"],
    citedSentences: 2
  });
  expect(await drawnTemplate(page)).toBe("document");
});

test("a craft record, a hub and an essay are read from their markup", async ({ page }) => {
  await page.setContent(
    `<article data-testid="craft-without-monograph"><h1>Kasuti Embroidery</h1><div data-testid="typographic-plate"></div><dl data-testid="fact-grid"><dt>Family</dt><dd>Textiles</dd><dt>Home state</dt><dd>Karnataka</dd></dl>` +
      `<div data-testid="empty-state"><h2>Start the research on Kasuti Embroidery</h2><a href="/ask?q=a">A</a><a href="/ask?q=b">B</a><a href="/crafts">All crafts</a></div></article>`
  );
  expect(await page.evaluate(recordShape, { root: RECORD_ROOT, rail: RAIL_LINKS })).toEqual({ heading: "Kasuti Embroidery", facts: 2, start: "Start the research on Kasuti Embroidery", questions: 2, plate: true, rail: 0, citeThis: false });
  expect(await drawnTemplate(page)).toBe("record");
  await page.setContent(`<div data-testid="category-hub"><div data-testid="hub-plate"><h1><span>Textiles</span></h1></div><section data-testid="collection-shelf"><a data-testid="collection-plate"></a><a data-testid="photo-card"></a></section></div>`);
  expect(await page.evaluate(hubShape, HUB_ROOT)).toEqual({ heading: "Textiles", plate: true, shelves: 1, plates: 2, chapters: 0 });
  await page.setContent(
    `<article data-testid="answer-view"><h1>Why alum?</h1><div data-testid="answer-lede"><p data-testid="answer-sentence">One<button data-testid="citation-chip">1</button></p><p data-testid="answer-sentence">Two</p></div>` +
      `<div data-testid="answer-actions"><button>Save</button><button>Cite this answer</button></div></article>`
  );
  expect(await page.evaluate(essayShape, ESSAY_ROOT)).toEqual({ question: "Why alum?", lede: 2, ledeCited: 1, actions: ["Save", "Cite this answer"] });
});

test("the tabbed page is told apart from a document and a record", async ({ page }) => {
  expect(Object.keys(CRAFT_TEMPLATES)).toEqual(["document", "tabbed", "record"]);
  await page.setContent(`<section data-testid="craft-panel-overview"><p>Overview</p></section>`);
  expect(await drawnTemplate(page)).toBe("tabbed");
});

test("each painted capture stays within Chromium's 16384 device pixels and never spans more than eight screens", () => {
  expect(segmentScreens({ screen: 1194, ratio: 2.5 })).toBe(5);
  expect(segmentScreens({ screen: 844, ratio: 2.625 })).toBe(7);
  expect(segmentScreens({ screen: 900, ratio: 1 })).toBe(8);
  expect(segmentScreens({ screen: 20_000, ratio: 1 })).toBe(1);
});

test("nav labels are read without their counts, unread badges or hidden words", async ({ page }) => {
  await page.setContent(
    `<nav aria-label="Main"><a href="/ask">Ask</a><a href="/saved">Saved<span data-testid="unread-notes"><span aria-hidden="true">2</span><span class="sr-only">, 2 unread</span></span></a>` +
      `<a href="/admin/access"><svg></svg><span>Who may sign in</span><span title="3 people are waiting">3 waiting</span></a></nav>`
  );
  expect(await labelsOf(page.getByRole("navigation", { name: "Main" }).locator("a"))).toEqual(["Ask", "Saved", "Who may sign in"]);
});
