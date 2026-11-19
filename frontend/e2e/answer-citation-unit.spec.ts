import { expect, test } from "@playwright/test";

import { answerAddress, answerBibtex, answerCitationIn, answerCitationText, type AnswerCitation } from "@/lib/answerCitation";

const ANSWER: AnswerCitation = {
  explainerId: "0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9",
  version: 2,
  question: "How does indigo turn blue on Kutch Ajrakh cloth?",
  answeredAt: "2026-11-17T10:00:00Z",
  sources: 11,
  origin: "https://kalavigyan.vercel.app/",
  path: null,
  accessedAt: new Date("2026-11-18T08:00:00Z")
};
const ADDRESS = "https://kalavigyan.vercel.app/ask?explainer=0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9&version=2";
const PUBLISHER = "IIT Kharagpur, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform";

test("the text citation names the question, the version, the answer date, the publisher, the versioned address and the access date", () => {
  expect(answerAddress(ANSWER)).toBe(ADDRESS);
  expect(answerCitationText(ANSWER)).toBe(`KalaVigyan. “How does indigo turn blue on Kutch Ajrakh cloth?” Answer, version 2, answered 17 November 2026. ${PUBLISHER}. ${ADDRESS}. Accessed 18 November 2026.`);
  expect(answerCitationText({ ...ANSWER, question: "Alum and madder on cotton", answeredAt: null })).toBe(`KalaVigyan. “Alum and madder on cotton.” Answer, version 2. ${PUBLISHER}. ${ADDRESS}. Accessed 18 November 2026.`);
});

test("BibTeX is a misc entry with the url, its date and the access date, and escapes TeX's own characters", () => {
  const lines = answerBibtex(ANSWER).split("\n");
  expect(lines[0]).toBe("@misc{kalavigyan_answer_0b1c2d3e_v2,");
  expect(lines).toContain("  title = {How does indigo turn blue on Kutch Ajrakh cloth?},");
  expect(lines).toContain("  author = {{KalaVigyan}},");
  expect(lines).toContain(`  publisher = {${PUBLISHER}},`);
  expect(lines).toContain("  version = {2},");
  expect(lines).toContain("  date = {2026-11-17},");
  expect(lines).toContain("  year = {2026},");
  expect(lines).toContain(`  howpublished = {\\url{${ADDRESS}}},`);
  expect(lines).toContain(`  url = {${ADDRESS}},`);
  expect(lines).toContain("  urldate = {2026-11-18},");
  expect(lines).toContain("  note = {Answer, drawn from 11 sources. Accessed 18 November 2026}");
  expect(lines.at(-1)).toBe("}");
  expect(answerBibtex({ ...ANSWER, question: "Alum & iron at 50% strength" })).toContain("  title = {Alum \\& iron at 50\\% strength},");
});

test("a shared answer is cited at its shared address, and the style picks the form", () => {
  const shared = { ...ANSWER, path: "/shared/answers/AbCdEfGhIjKlMnOpQrStUv" };
  expect(answerAddress(shared)).toBe("https://kalavigyan.vercel.app/shared/answers/AbCdEfGhIjKlMnOpQrStUv");
  expect(answerCitationIn("text", shared)).toContain("https://kalavigyan.vercel.app/shared/answers/AbCdEfGhIjKlMnOpQrStUv. Accessed");
  expect(answerCitationIn("bibtex", shared).startsWith("@misc{")).toBe(true);
});
