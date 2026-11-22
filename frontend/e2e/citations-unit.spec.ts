import { expect, test } from "@playwright/test";

import { chemistryTex, renderChemistry } from "@/lib/chemistry";
import { citationsBySource, doiUrl, highlightQuote, listedSourceNumbers, safeOutboundUrl, sourceHref, sourceKindLabel, sourceNumbers, sourceReliabilityLabel } from "@/lib/citations";
import type { AnswerSection, Citation } from "@/lib/types";

const cite = (sourceId: string): Citation => ({
  id: `c-${sourceId}`,
  claimId: `k-${sourceId}`,
  sourceId,
  quote: null,
  locator: null,
  context: null,
  evidence: "QUOTED",
  level: "PROVISIONAL"
});

test("sources are numbered by first appearance", () => {
  const sections: AnswerSection[] = [
    { id: "a", heading: "", sentences: [{ id: "1", text: "x", level: "PROVISIONAL", citations: [cite("s2"), cite("s1")] }] },
    { id: "b", heading: "", sentences: [{ id: "2", text: "y", level: "PROVISIONAL", citations: [cite("s1"), cite("s3")] }] }
  ];
  expect([...sourceNumbers(sections).entries()]).toEqual([
    ["s2", 1],
    ["s1", 2],
    ["s3", 3]
  ]);
});

test("only https links leave the site", () => {
  expect(safeOutboundUrl("https://example.org/a")).toBe("https://example.org/a");
  expect(safeOutboundUrl("http://example.org/a")).toBeNull();
  expect(safeOutboundUrl("javascript:alert(1)")).toBeNull();
  expect(safeOutboundUrl("data:text/html,hi")).toBeNull();
});

test("a DOI becomes a doi.org link when there is no URL", () => {
  expect(doiUrl("10.1016/j.dyepig.2020.108123")).toBe("https://doi.org/10.1016/j.dyepig.2020.108123");
  expect(doiUrl("doi:10.1000/xyz")).toBe("https://doi.org/10.1000/xyz");
  expect(doiUrl("not a doi")).toBeNull();
  expect(sourceHref({ url: null, doi: "10.1000/xyz" })).toBe("https://doi.org/10.1000/xyz");
});

test("the quoted passage is marked inside its context", () => {
  const parts = highlightQuote("Alum   forms a lake\nwith alizarin on cotton.", "forms a lake with alizarin");
  expect(parts).toEqual([
    { text: "Alum ", mark: false },
    { text: "forms a lake with alizarin", mark: true },
    { text: " on cotton.", mark: false }
  ]);
});

test("a quote missing from its context is still shown, marked", () => {
  expect(highlightQuote("Other text.", "the quote")).toEqual([{ text: "the quote", mark: true }]);
  expect(highlightQuote(null, null)).toEqual([]);
});

test("chemical equations go through mhchem with trust off", () => {
  expect(chemistryTex("Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2")).toBe("\\ce{Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2}");
  expect(chemistryTex("\\ce{H2O}")).toBe("\\ce{H2O}");
  const html = renderChemistry("Al2Si2O5(OH)4 -> Al2Si2O7 + 2 H2O", true);
  expect(html).toContain("katex");
  expect(html).not.toContain("<script");
});

test("source types and reliability tiers read as words in the source dialog", () => {
  expect(sourceKindLabel("WEB_PAGE")).toBe("Web page");
  expect(sourceKindLabel("MEDIA")).toBe("Media file");
  expect(sourceKindLabel("SOMETHING_NEW")).toBe("Other");
  expect(sourceReliabilityLabel("A")).toBe("A · peer-reviewed or official");
  expect(sourceReliabilityLabel("C")).toBe("C · general web");
});

const passage = (sourceId: string, claimId: string, quote: string | null, locator: string | null = null): Citation => ({
  id: `${claimId}:${sourceId}:${quote ?? "inferred"}`,
  claimId,
  sourceId,
  quote,
  locator,
  context: null,
  evidence: quote === null ? "INFERRED" : "QUOTED",
  level: "PROVISIONAL"
});

test("a sentence citing sources 1 4 1 4 5 1 shows 1 4 5, each once, with every quote behind its number", () => {
  const numbers = new Map([
    ["gi-journal", 1],
    ["edwards", 4],
    ["karolia", 5]
  ]);
  const citations = [
    passage("gi-journal", "C003", "printed on both sides", "p. 6"),
    passage("edwards", "C006", "resist and mordant"),
    passage("gi-journal", "C006", "sixteen stages", "p. 7"),
    passage("edwards", "C007", "resist and mordant"),
    passage("karolia", "C007", "harda and alum"),
    passage("gi-journal", "C007", "printed on both sides", "p. 6")
  ];
  const groups = citationsBySource(citations, numbers);
  expect(groups.map((group) => group.number)).toEqual([1, 4, 5]);
  expect(groups[0].citations.map((citation) => [citation.quote, citation.locator])).toEqual([
    ["printed on both sides", "p. 6"],
    ["sixteen stages", "p. 7"]
  ]);
  expect(groups[1].citations.map((citation) => citation.claimId)).toEqual(["C006"]);
  for (const citation of citations) {
    const group = groups.find((found) => found.sourceId === citation.sourceId);
    expect(group?.citations.some((kept) => kept.quote === citation.quote && kept.locator === citation.locator)).toBe(true);
  }
});

test("a source the reading has not numbered follows the numbered ones in the order it was cited", () => {
  const groups = citationsBySource([passage("later", "C1", "a"), passage("first", "C2", "b"), passage("unknown", "C3", null)], new Map([["first", 2], ["later", 9]]));
  expect(groups.map((group) => [group.sourceId, group.number])).toEqual([
    ["first", 2],
    ["later", 9],
    ["unknown", null]
  ]);
  expect(groups[2].citations[0].evidence).toBe("INFERRED");
});

test("a listed source keeps the number the page gave it and new sources are numbered after the page's", () => {
  const numbered = new Map([
    ["a", 1],
    ["b", 2]
  ]);
  expect([...listedSourceNumbers([{ id: "b" }, { id: "x" }, { id: "x" }, { id: "y" }], numbered).entries()]).toEqual([
    ["a", 1],
    ["b", 2],
    ["x", 3],
    ["y", 4]
  ]);
  expect([...listedSourceNumbers([{ id: "x" }, { id: "y" }]).entries()]).toEqual([
    ["x", 1],
    ["y", 2]
  ]);
});
