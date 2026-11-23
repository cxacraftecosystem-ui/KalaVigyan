import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { checkedCraftPage, readingSourceIds, shownSentences } from "@/lib/craftPageChecks";
import { CRAFT_PAGE_PATH, craftEdition, craftPageShape, UNREAD_CHAPTERS, type CraftPage } from "@/lib/craftPageContract";
import {
  claimIndex,
  craftTabs,
  glossaryMeaning,
  overviewHasContent,
  pageSourceNumbers,
  pageSourcesById,
  registerFacts,
  shownSentence,
  shownTab,
  sourceGroups,
  stageGroups,
  termAliases
} from "@/lib/craftPageView";
import { citationsBySource } from "@/lib/citations";
import { placeDistricts, placeRows } from "@/lib/craftPlaces";
import { parseShape, ShapeError } from "@/lib/shape";

import { CRAFT_PAGE_GOLDEN, curatedPage, emptyPage, pageEvidence, rawPage, REGISTER_PAGE_GOLDEN, uncuratedPage } from "./craftPageFixture";
import { eagerModules, FRONTEND } from "./moduleGraph";
import { curatedOverviewProblems, overviewNote } from "./production/checks";

const GI_JOURNAL = "c1fa6a39-5386-5d7d-8623-393e1e61f6db";
const RHYTHM_OF_BLUES = "def6894b-e67b-552b-bd8c-bfc980cf3bb0";
const CASTE_DRESS = "29ff4c54-3b6b-55b3-94d8-4bf24abb1190";
const OUTSIDE = "00000000-0000-4000-8000-000000000001";
const PERSONAL_KEYS = /"(userId|answerId|createdFromAnswerId|requestedById|askedBy|email)":/;

function refused(edit: (body: CraftPage) => void): () => CraftPage {
  return () => {
    const body = rawPage();
    edit(body);
    return checkedCraftPage(parseShape(craftPageShape, body));
  };
}

test("the Kutch Ajrakh page parses as the backend wrote it, curated, with every part filled", () => {
  const page = curatedPage();
  expect(page.curated).toBe(true);
  expect(page.curation).toMatchObject({ version: 3, coverage: "FULL" });
  expect(page.overview.lede).toHaveLength(3);
  expect(page.overview.keyFacts.map((fact) => fact.label)).toEqual(["GI status", "Centres", "Makers and wearers", "Colours", "Dyes and mordants", "Stages", "Time per piece", "Resists"]);
  expect(page.overview.sections.map((section) => section.title)).toEqual(["History", "How it is made", "The chemistry", "Materials", "Geography and water", "Economics", "Design"]);
  expect([page.sourcesDiffer.length, page.places.length, page.communities.length, page.glossary.length, page.pictures.length, page.openQuestions.length]).toEqual([14, 12, 8, 17, 10, 4]);
  expect([page.claims.length, page.sources.length, page.evidence.hypotheses.length]).toEqual([143 + 4, 24 + 5 + 7, 5]);
});

test("the client refuses a page that names a claim or source it does not list", () => {
  expect(refused((body) => (body.overview.keyFacts[0].claimIds = [OUTSIDE]))).toThrow(ShapeError);
  expect(refused((body) => (body.claims[0].citations[0].sourceId = OUTSIDE))).toThrow(/source/);
  expect(refused((body) => body.claims.push({ ...body.claims[0] }))).toThrow(/once/);
});

test("the client refuses a hypothesis among the facts, a fact among the hypotheses, and a claim filed twice", () => {
  expect(refused((body) => (body.overview.lede[0].level = "HYPOTHESIS"))).toThrow(/hypothesis/);
  expect(refused((body) => pageEvidence(body).hypotheses.push(pageEvidence(body).groups[0].subjects[0].entries[0]))).toThrow(ShapeError);
  expect(refused((body) => (pageEvidence(body).hypotheses = []))).toThrow(/filed/);
});

test("the client refuses an equation on an unbalanced reaction and a place or curation off the contract", () => {
  expect(refused((body) => (body.process.stages[4].reactions[0].equation = "Fe -> Fe"))).toThrow(/balanced/);
  expect(refused((body) => (body.places[0] = { ...body.places[0], kind: "PLANET" as never }))).toThrow(ShapeError);
  expect(refused((body) => (body.curation = null))).toThrow(/curated/);
  expect(refused((body) => (body.process.stages[0].order = 0))).toThrow(ShapeError);
});

test("a sentence carries the citations of every claim it rests on, and its term spans", () => {
  const page = curatedPage();
  const index = claimIndex(page);
  const lede = shownSentence(index, page.overview.lede[0]);
  expect(lede.citations.map((citation) => citation.sourceId)).toEqual([GI_JOURNAL, RHYTHM_OF_BLUES, CASTE_DRESS]);
  const scouring = shownSentence(index, page.overview.sections[1].sentences[0]);
  expect(scouring.terms).toEqual([{ text: "saaj", termKey: "saaj" }]);
});

test("sources are numbered in reading order, every page source numbered once, region sources after", () => {
  const page = curatedPage();
  const extra = { ...page.sources[0], id: OUTSIDE, title: "District register" };
  const numbers = pageSourceNumbers(page, [extra]);
  expect([numbers.get(GI_JOURNAL), numbers.get(RHYTHM_OF_BLUES), numbers.get(CASTE_DRESS)]).toEqual([1, 2, 3]);
  expect(numbers.size).toBe(37);
  expect(numbers.get(OUTSIDE)).toBe(37);
  expect(new Set(numbers.values()).size).toBe(37);
  expect(pageSourcesById(page, [extra]).get(OUTSIDE)?.title).toBe("District register");
});

test("every sentence of the page shows each source once, numbers ascending, with every quote behind its number", () => {
  const page = curatedPage();
  const index = claimIndex(page);
  const numbers = pageSourceNumbers(page, []);
  const sentences = [...page.overview.lede, ...page.overview.sections.flatMap((section) => section.sentences)];
  expect(sentences.length).toBeGreaterThan(0);
  for (const sentence of sentences) {
    const citations = shownSentence(index, sentence).citations;
    const cited = [...new Set(citations.map((citation) => numbers.get(citation.sourceId)))].sort((a, b) => (a ?? 0) - (b ?? 0));
    const groups = citationsBySource(citations, numbers);
    expect(groups.map((group) => group.number)).toEqual(cited);
    for (const citation of citations) {
      const group = groups.find((found) => found.sourceId === citation.sourceId);
      expect(group?.citations.some((kept) => kept.quote === citation.quote && kept.locator === citation.locator)).toBe(true);
    }
  }
});

test("stages are numbered only where the response orders them; unordered stages stand apart", () => {
  const { numbered, unnumbered } = stageGroups(curatedPage().process.stages);
  expect(numbered.map((stage) => stage.order)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
  expect(unnumbered.map((stage) => stage.name)).toEqual(["Sun bleaching on the river bank", "Final wash", "Block carving"]);
  const shuffled = stageGroups([...curatedPage().process.stages].reverse());
  expect(shuffled.numbered.map((stage) => stage.name).slice(0, 2)).toEqual(["Scouring", "Myrobalan treatment"]);
});

test("a place with several roles is one row with every role; districts where the craft is made are told apart", () => {
  const page = curatedPage();
  const rows = placeRows(page.places);
  expect(rows.map((row) => [row.name, row.roles])).toEqual([
    ["Ajrakhpur", ["PRACTISED", "MIGRATED_TO"]],
    ["Dhamadka", ["PRACTISED", "HISTORIC_CENTRE", "MIGRATED_FROM"]],
    ["Khavda", ["PRACTISED", "HISTORIC_CENTRE"]],
    ["Barmer", ["PRACTISED"]],
    ["Sindh", ["PRACTISED", "ORIGIN"]],
    ["Pethapur", ["MATERIAL_SOURCE"]],
    ["Dhamadka River (Suran)", ["MATERIAL_SOURCE"]]
  ]);
  expect(rows.map((row) => row.where)).toEqual([
    "Kachchh district, Gujarat",
    "Kachchh district, Gujarat",
    "Kachchh district, Gujarat",
    "Rajasthan",
    "Pakistan",
    "Gandhinagar district, Gujarat",
    "Kachchh district, Gujarat"
  ]);
  const districts = placeDistricts(page.places);
  expect([...districts.made].sort()).toEqual([449, 90].sort());
  expect([...districts.named.entries()].sort()).toEqual([
    [446, "Gandhinagar"],
    [449, "Kachchh"],
    [90, "Barmer"]
  ]);
});

test("sources group by reliability A to D, each source in its own grade once", () => {
  const page = curatedPage();
  const groups = sourceGroups(page.sources, pageSourceNumbers(page, []));
  expect(groups.map((group) => [group.label, group.sources.length])).toEqual([
    ["A · peer-reviewed or official", 21],
    ["B · reputable reference", 9],
    ["C · general web", 5],
    ["D · unknown", 1]
  ]);
  for (const group of groups) for (const source of group.sources) expect(source.reliability).toBe(group.reliability);
  const unrated = sourceGroups([{ ...page.sources[0], reliability: null }], new Map());
  expect(unrated.map((group) => group.label)).toEqual(["Not rated"]);
});

test("a glossary meaning shows only with its citations; aliases leave out the label", () => {
  const page = curatedPage();
  const saaj = page.glossary[0];
  expect(glossaryMeaning(saaj)).toContain("scouring of the cloth");
  expect(termAliases(saaj)).toEqual(["saaji", "neerani"]);
  expect(glossaryMeaning({ ...saaj, claimIds: [] })).toBeNull();
  expect(glossaryMeaning(uncuratedPage().glossary[0])).toBeNull();
});

test("the Evidence tab shows whenever the page holds evidence, for every reader", () => {
  const page = curatedPage();
  expect(craftTabs(page, { sources: true, evidence: false, science: false })).toEqual(["overview", "process", "region", "sources"]);
  expect(craftTabs(page, { sources: true, evidence: true, science: false })).toEqual(["overview", "process", "region", "sources", "evidence"]);
  expect(shownTab("evidence", craftTabs(page, { sources: true, evidence: false, science: false }))).toBe("overview");
  expect(shownTab("process", craftTabs(page, { sources: true, evidence: false, science: false }))).toBe("process");
});

test("every reader's page holds All evidence; the client refuses a page served without it", () => {
  const page = curatedPage();
  const filed = [...page.evidence.groups.flatMap((group) => group.subjects.flatMap((subject) => subject.entries)), ...page.evidence.hypotheses];
  expect(filed.flatMap((entry) => [entry.claimId, ...entry.foldedIds]).sort()).toEqual(page.claims.map((claim) => claim.id).sort());
  expect(
    refused((body) => {
      (body as { evidence: unknown }).evidence = null;
    })
  ).toThrow(ShapeError);
});

test("the masthead names the craft, its family and kind, its GI date as cited, its place and its curation", () => {
  const page = curatedPage();
  const { masthead } = page;
  expect([masthead.name, masthead.kicker]).toEqual(["Kutch Ajrakh", { family: "Textiles", kind: "Hand block printing" }]);
  expect([masthead.place, masthead.palette]).toEqual(["Kachchh, Gujarat", "indigo"]);
  expect(masthead.gi?.status).toBe("REGISTERED");
  expect(masthead.gi?.on).toBe("2024-04-22");
  expect(masthead.gi?.citations.length).toBeGreaterThan(0);
  expect(masthead.provenance.basis).toBe("CURATED");
  expect(masthead.provenance.curatedOn).toBe(page.curation?.curatedAt.slice(0, 10));
  expect(refused((body) => (body.masthead.provenance.curatedOn = null))).toThrow(/curation day/);
  expect(refused((body) => body.masthead.gi && (body.masthead.gi.citations = []))).toThrow(/GI date/);
});

test("Cite this names the lower-case versioned address of the curation the page shows", () => {
  const page = curatedPage();
  const version = page.curation?.version;
  expect(page.cite).toMatchObject({ url: `/crafts/kutch-ajrakh/v${version}`, version, curatedOn: page.masthead.provenance.curatedOn });
  expect(page.cite?.bibtex.startsWith("@misc{")).toBe(true);
  expect(refused((body) => body.cite && (body.cite.url = "/crafts/kutch-ajrakh"))).toThrow(/versioned/);
});

test("sources are listed once in reading order, grouped, borrowed ones naming their monograph, each supporting a sentence the page shows", () => {
  const page = curatedPage();
  const head = new Set(shownSentences(page).flatMap((sentence) => sentence.citations.map((citation) => citation.sourceId)));
  for (const source of page.sources) {
    expect(source.supports >= (head.has(source.id) ? 1 : 0)).toBe(true);
    expect(source.from !== null).toBe(source.group === "FAMILY" || source.group === "KIN");
  }
  const order = readingSourceIds(page);
  expect(page.sources.slice(0, order.length).map((source) => source.id)).toEqual(order);
  expect(refused((body) => (body.sources[0].group = "FAMILY"))).toThrow(/monograph/);
  expect(refused((body) => body.sources.push(body.sources[0]))).toThrow(/once/);
});

test("an uncurated craft keeps its stored sections and evidence; a craft with nothing shows only what the register holds", () => {
  const uncurated = uncuratedPage();
  expect(uncurated.overview.sections.every((section) => section.basis === "STORED_CLAIMS" && section.sentences.length <= 8)).toBe(true);
  expect(overviewHasContent(uncurated)).toBe(true);
  const empty = emptyPage();
  expect(overviewHasContent(empty)).toBe(false);
  expect(craftTabs(empty, { sources: false, evidence: true, science: false })).toEqual(["overview", "region"]);
  expect(registerFacts(empty.craft)).toEqual([
    { label: "Category", value: "Textiles based Craft Category" },
    { label: "Kind", value: "Hand Block Printing" },
    { label: "GI status", value: "Registered geographical indication" },
    { label: "Practised in", value: "Gujarat" },
    { label: "Origin", value: "Gujarat" }
  ]);
});

test("the production Overview check needs a curated page's lede and key facts on screen", () => {
  const served = { curated: true, version: 1, coverage: "FULL", lede: 3, keyFacts: 8 };
  expect(curatedOverviewProblems(served, { lede: 3, keyFacts: 8 })).toEqual([]);
  expect(curatedOverviewProblems(served, { lede: 0, keyFacts: 8 })).toEqual(["the lede shows 0 of its 3 sentences"]);
  expect(curatedOverviewProblems(served, { lede: 3, keyFacts: 7 })).toEqual(["the key facts show 7 of 8"]);
  expect(curatedOverviewProblems({ ...served, lede: 0, keyFacts: 0 }, { lede: 0, keyFacts: 0 })).toEqual(["the curated page serves no lede", "the curated page serves no key facts"]);
  expect(curatedOverviewProblems({ ...served, curated: false, lede: 0, keyFacts: 0 }, { lede: 0, keyFacts: 0 })).toEqual([]);
  expect(overviewNote(served)).toBe("curated: version 1, FULL coverage");
  expect(overviewNote({ ...served, curated: false })).toBe("not curated");
});

test("the craft page loads the monograph or the craft list's record only when it draws it, draws no tabs and mounts no generator", () => {
  const route = readFileSync(join(FRONTEND, "app", "(reading)", "crafts", "[slug]", "page.tsx"), "utf8");
  const lazy = [...route.matchAll(/dynamic\(\(\) => import\("([^"]+)"\)/g)].map((found) => found[1]);
  expect(lazy).toEqual(["@/components/monograph/MonographShellPage", "@/components/monograph/MonographDocumentPage", "@/components/craft/CraftWithoutMonograph"]);
  const eager = [...eagerModules("@/app/(reading)/crafts/[slug]/page")];
  expect(eager.filter((file) => /components\/(monograph|craft)\//.test(file))).toEqual([]);
  const graph = [...new Set([...eager, ...lazy.flatMap((entry) => [...eagerModules(entry)])])];
  const texts = graph.map((file) => readFileSync(join(FRONTEND, file), "utf8"));
  expect(graph).toContain("lib/craftPageContract.ts");
  expect(graph).toContain("lib/monographDocumentShape.ts");
  expect(graph).toContain("components/monograph/MonographShellPage.tsx");
  expect(graph).toContain("components/monograph/MonographDocumentPage.tsx");
  expect(graph).toContain("components/craft/CraftWithoutMonograph.tsx");
  const shellPage = [...eagerModules("@/components/monograph/MonographShellPage")];
  expect(shellPage.filter((file) => /MonographDocumentPage|MonographChapters|ComponentSlot\.tsx/.test(file))).toEqual([]);
  expect([...eagerModules("@/components/answer/ChemEquation")]).not.toContain("lib/chemistry.ts");
  expect(graph).toContain("components/monograph/kinds/blocks/LazyAnswerBlockView.tsx");
  expect(graph.filter((file) => /kinds\/blocks\/AnswerBlockView|components\/answer\/blockRenderers/.test(file))).toEqual([]);
  expect(graph.filter((file) => /CraftScreen|CraftTabs|CraftReference|craftMedia|StageMedia|mediaContract/.test(file))).toEqual([]);
  expect(texts.filter((text) => /\/(profile|process)`/.test(text))).toEqual([]);
});

test("the client drops the chapters no screen draws, and reads a page with or without them (decision 0162)", () => {
  const sent = rawPage() as CraftPage & { chapters?: unknown };
  expect(Array.isArray(sent.chapters)).toBe(true);
  const read = curatedPage();
  expect(UNREAD_CHAPTERS in read).toBe(false);
  const without: Record<string, unknown> = { ...sent };
  delete without[UNREAD_CHAPTERS];
  expect(checkedCraftPage(parseShape(craftPageShape, without))).toEqual(read);
});

test("a versioned address is a monograph edition, and the page route takes no version", () => {
  expect([craftEdition("v2"), craftEdition("v0"), craftEdition("2"), craftEdition("v2x")]).toEqual([2, null, null, null]);
  expect(CRAFT_PAGE_PATH("Kutch-Ajrakh")).toBe("/crafts/Kutch-Ajrakh/page");
  const page = curatedPage();
  const edition = page.cite?.url.split("/").pop() ?? "";
  expect(craftEdition(edition)).toBe(page.curation?.version);
  expect(page.cite?.text.endsWith(page.cite.url)).toBe(true);
});

test("no golden carries a user or an answer id", () => {
  for (const golden of [CRAFT_PAGE_GOLDEN, REGISTER_PAGE_GOLDEN]) expect(readFileSync(golden, "utf8")).not.toMatch(PERSONAL_KEYS);
});
