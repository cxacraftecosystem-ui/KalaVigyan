import { expect, test } from "@playwright/test";

import {
  CONTRIBUTION_CRAFT,
  CONTRIBUTION_FIELD,
  CONTRIBUTION_STATEMENT,
  closedReading,
  documentHolds,
  fieldClaims,
  proposalArguments,
  queuedProposal,
  quoteFrom,
  readerFactProblems,
  readerProblems,
  readText,
  sourceChoices
} from "./mcpContribution";

const STUDY = { id: "s1", url: "https://www.jeb.co.in/journal_issues/200701_jan07/paper_14.pdf", title: "Genotoxicity of textile dyes used in Sanganer", licence: null };
const JUNK = { id: "s2", url: "https://example.org/aa.pdf", title: "aa.MDI", licence: null };
const PLAIN = { id: "s3", url: "http://example.org/plain", title: "A plain web page here", licence: null };
const CLAIM = "0d7c0000-0000-4000-8000-000000000001";
const SHOWN_REPLY = {
  outcome: "PUBLISHED",
  claimId: CLAIM,
  message: "Published, and approved at once because your account reviews contributions. Readers see it now at https://kalavigyan.example/crafts/Sanganeri-Hand-Block-Printing among the page's cited Policy facts.",
  readers: { shown: true, reason: null }
};

test("only https sources with a title of three words or more are tried", () => {
  expect(sourceChoices({ sources: [JUNK, PLAIN, STUDY] })).toEqual([{ url: STUDY.url, title: STUDY.title, licence: null }]);
});

test("a quote is a digit-free sentence of a closed reading, cut at a sentence end", () => {
  const reading = {
    readable: true,
    openLicence: false,
    passages: [{ text: "Table 2. Results of 12 dyes. Most textile dyes used in the hand block printing units have not been evaluated for health impact. Short one." }]
  };
  expect(readText({ text: reading, quotes: [] })).toEqual(reading);
  expect(closedReading(reading)).toBe(true);
  expect(closedReading({ ...reading, openLicence: true })).toBe(false);
  expect(quoteFrom(reading)).toBe("Most textile dyes used in the hand block printing units have not been evaluated for health impact.");
  expect(quoteFrom({ passages: [{ text: "Only 12 of 13 dyes, said in 2007." }] })).toBeNull();
});

test("the proposal is one test fact of the craft's field with its own key and the quote", () => {
  const body = proposalArguments({ url: STUDY.url, title: STUDY.title, licence: null }, "a quote of forty characters or more, word for word", "1732");
  const [fact] = body.facts as Record<string, unknown>[];
  expect([fact.craft_slug, fact.field, fact.statement, fact.idempotency_key]).toEqual([CONTRIBUTION_CRAFT, CONTRIBUTION_FIELD, CONTRIBUTION_STATEMENT, "release-check:1732"]);
  expect(/\d/u.test(CONTRIBUTION_STATEMENT)).toBe(false);
  expect(queuedProposal({ items: [{ accepted: true, ticket: { proposalId: "p1" } }] })).toEqual({ id: "p1", problems: [] });
  expect(queuedProposal({ items: [{ accepted: false, problem: "terms needed" }] }).problems).toEqual(["propose_facts did not queue the fact: terms needed"]);
});

test("a published reply must say readers see the fact, and a hidden one fails the check", () => {
  expect(readerProblems(SHOWN_REPLY)).toEqual([]);
  expect(readerProblems({ ...SHOWN_REPLY, readers: { shown: false, reason: "NO_SHOWN_SOURCE" } })).toEqual([
    `the reply says readers cannot see the fact (NO_SHOWN_SOURCE): ${SHOWN_REPLY.message}`
  ]);
  expect(readerProblems({ ...SHOWN_REPLY, readers: undefined })).toEqual(["the reply does not say where readers see the fact"]);
});

test("a signed-out reader sees the fact cited by the closed page without its words, on the page and in the count", () => {
  const facts = { sources: [STUDY], facts: [{ id: CLAIM, citations: [{ sourceId: "s1", quote: null }] }] };
  const source = { url: STUDY.url, title: STUDY.title, licence: null };
  expect(readerFactProblems(facts, CLAIM, source)).toEqual([]);
  expect(readerFactProblems({ ...facts, facts: [{ id: CLAIM, citations: [{ sourceId: "s1", quote: "closed words" }] }] }, CLAIM, source)).toEqual([
    "a signed-out reader is shown the closed page's words"
  ]);
  expect(readerFactProblems({ ...facts, facts: [] }, CLAIM, source)).toEqual([`get_facts does not show fact ${CLAIM} to a signed-out reader`]);
  expect(documentHolds({ content: { units: { "fact-policy-1": { claimIds: [CLAIM] } } } }, CLAIM)).toBe(true);
  expect(documentHolds({ content: { units: {} } }, CLAIM)).toBe(false);
  expect(fieldClaims({ fields: [{ field: "POLICY", claims: 3 }] }, "POLICY")).toBe(3);
});
