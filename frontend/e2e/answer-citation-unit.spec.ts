import { expect, test } from "@playwright/test";

import { answerAddress, answerCitable } from "@/lib/answerCitation";
import { citation } from "@/lib/monographCite";

const ANSWER = { explainerId: "0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9", version: 2, question: "  Why does alum hold the red on Kutch Ajrakh cloth  " };
const SIGNED_IN = { origin: "https://kalavigyan.vercel.app/", path: null };
const ADDRESS = "https://kalavigyan.vercel.app/ask?explainer=0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9&version=2";
const PUBLISHER = "IIT Kharagpur, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform";

test("an answer is cited at its versioned address, or at its shared address on a shared page", () => {
  expect(answerAddress(ANSWER, SIGNED_IN)).toBe(ADDRESS);
  expect(answerAddress(ANSWER, { origin: "https://kalavigyan.vercel.app", path: "/shared/answers/AbCdEfGhIjKlMnOpQrStUv" })).toBe("https://kalavigyan.vercel.app/shared/answers/AbCdEfGhIjKlMnOpQrStUv");
});

test("the answer's citation is the shared Cite this form: the trimmed question, the answer and its version, the publisher, the address and the access date", () => {
  const cite = answerCitable(ANSWER, SIGNED_IN);
  expect(cite).toEqual({ kind: "answer", title: "Why does alum hold the red on Kutch Ajrakh cloth", version: 2, url: ADDRESS, key: "kalavigyan_answer_0b1c2d3e_v2" });
  const accessed = new Date(2026, 10, 18, 9, 0, 0);
  expect(citation(cite, "text", accessed)).toBe(`KalaVigyan. “Why does alum hold the red on Kutch Ajrakh cloth.” Answer, version 2. ${PUBLISHER}. ${ADDRESS}. Accessed 18 November 2026.`);
  const bibtex = citation(cite, "bibtex", accessed).split("\n");
  expect(bibtex[0]).toBe("@misc{kalavigyan_answer_0b1c2d3e_v2,");
  expect(bibtex).toContain(`  url = {${ADDRESS}},`);
  expect(bibtex).toContain("  urldate = {2026-11-18},");
});
