import { deflateRawSync } from "node:zlib";

import { expect, test } from "@playwright/test";

import { NAV_ITEMS, isNavItemVisible } from "@/components/DynamicIslandNav";
import { canBuildLessons } from "@/lib/permissions";
import type { User, UserRole } from "@/lib/types";

import { readRepo } from "./phaseBFixture";
import { NAV_BY_ROLE } from "./production/checks";
import type { SourceRecord } from "./production/answers";
import { citationFileProblems, htmlDeckProblems, pdfLinks, pdfProblems, pptxProblems, zipEntries, type CitedSource } from "./production/exportFiles";
import { lessonSourceProblems } from "./production/exportProof";
import { PROFESSOR_SECRETS, lessonStep, professorProblems } from "./production/lessonProof";
import type { AnswersReport } from "./production/report";
import { summaryMarkdown } from "./production/summaryMarkdown";

type Entry = { number: number; apa: string; bibtex: string; ris: string; csl: Record<string, unknown> };

const CITATIONS = JSON.parse(readRepo("shared", "learning.citations.golden.json")) as { entries: Entry[] };
const VERSIONS = JSON.parse(readRepo("shared", "learning.versions.golden.json")) as { latest: { explainer: { sources: CitedSource[] } } };
const SOURCES = VERSIONS.latest.explainer.sources;
const STRAY: CitedSource = { title: "A source the explainer never cited", doi: "10.5555/stray", url: null };
const LINKED: CitedSource = { title: "Linked", doi: null, url: "https://example.org/a?b=1&c=(2)" };

function citationFiles(): Record<string, string> {
  const entries = CITATIONS.entries;
  return {
    txt: entries.map((entry) => `[${entry.number}] ${entry.apa}`).join("\n"),
    bib: entries.map((entry) => entry.bibtex).join("\n"),
    ris: entries.map((entry) => entry.ris).join(""),
    json: JSON.stringify(entries.map((entry) => entry.csl))
  };
}

function zipOf(files: Record<string, string>): Buffer {
  const locals: Buffer[] = [];
  const centrals: Buffer[] = [];
  let offset = 0;
  for (const [name, text] of Object.entries(files)) {
    const data = deflateRawSync(Buffer.from(text, "utf8"));
    const nameBytes = Buffer.from(name, "utf8");
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(8, 8);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt16LE(nameBytes.length, 26);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(8, 10);
    central.writeUInt32LE(data.length, 20);
    central.writeUInt16LE(nameBytes.length, 28);
    central.writeUInt32LE(offset, 42);
    locals.push(local, nameBytes, data);
    centrals.push(central, nameBytes);
    offset += local.length + nameBytes.length + data.length;
  }
  const directory = Buffer.concat(centrals);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(Object.keys(files).length, 10);
  end.writeUInt32LE(directory.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, directory, end]);
}

test("every citation file of the fixture carries every source of the explainer it was written from", () => {
  for (const [format, text] of Object.entries(citationFiles())) {
    expect(citationFileProblems(format, text, SOURCES), format).toEqual([]);
    expect(citationFileProblems(format, text, [...SOURCES, STRAY]), format).toHaveLength(1);
  }
});

test("a PDF opens with a page and carries each source's link, escaped parentheses read back", () => {
  const pdf = Buffer.from("%PDF-1.3\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /A << /S /URI /URI (https://example.org/a?b=1&c=\\(2\\)) >> >> endobj\n%%EOF\n", "latin1");
  expect([...pdfLinks(pdf)]).toEqual([LINKED.url]);
  expect(pdfProblems("the report PDF", pdf, [LINKED])).toEqual([]);
  expect(pdfProblems("the report PDF", pdf, [LINKED, STRAY])).toEqual(["the report PDF lacks the link of 1 of the explainer's sources: https://doi.org/10.5555/stray"]);
  expect(pdfProblems("the report PDF", Buffer.from("<html>", "latin1"), [])).toEqual(["the report PDF is not a whole PDF file"]);
});

test("a PPTX opens as a zip of slides whose links are the sources' links", () => {
  const deck = zipOf({
    "ppt/presentation.xml": "<p:presentation/>",
    "ppt/slides/slide1.xml": "<p:sld/>",
    "ppt/slides/_rels/slide1.xml.rels": '<Relationships><Relationship Target="https://example.org/a?b=1&amp;c=(2)" TargetMode="External"/></Relationships>'
  });
  expect([...zipEntries(deck).keys()]).toHaveLength(3);
  expect(pptxProblems("the lesson PPTX", deck, [LINKED])).toEqual([]);
  expect(pptxProblems("the lesson PPTX", deck, [STRAY])).toHaveLength(1);
  expect(pptxProblems("the lesson PPTX", Buffer.from("not a zip"), [])[0]).toContain("does not open");
});

test("a lesson deck opens as a whole HTML file of slides that carries the sources' links, entities read back", () => {
  const deck = Buffer.from(
    '<!doctype html>\n<html lang="en"><body><div class="slides"><section data-kind="SOURCES" data-number="5"><ol class="kv-list"><li value="1">Linked. https://example.org/a?b=1&amp;c=(2)</li></ol></section></div></body>\n</html>\n',
    "utf8"
  );
  expect(htmlDeckProblems("the lesson deck", deck, [LINKED])).toEqual([]);
  expect(htmlDeckProblems("the lesson deck", deck, [LINKED, STRAY])).toEqual(["the lesson deck lacks the link of 1 of the explainer's sources: https://doi.org/10.5555/stray"]);
  expect(htmlDeckProblems("the lesson deck", Buffer.from('<!doctype html>\n<html><div class="slides"></div></html>\n', "utf8"), [])).toEqual(["the lesson deck holds no slide"]);
  expect(htmlDeckProblems("the lesson deck", Buffer.from("%PDF-1.7", "latin1"), [])).toEqual(["the lesson deck is not a whole HTML file"]);
});

const PRODUCTION = "https://kalavigyan.vercel.app";
const PREVIEW = "https://kalavigyan-a1b2c3d4e-cxacraftecosystem-8028s-projects.vercel.app";
const PROFESSOR_ACCOUNT = { email: "e2e-professor@kalavigyan.example", password: "not-a-real-password", totpSecret: "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ" };

test("production proves a lesson pack as the Professor, fails without the Professor's secrets, and a preview only notes it", () => {
  expect(/Capability\.BUILD_LESSONS: (\w+),/.exec(readRepo("backend", "app", "core", "roles.py"))?.[1]).toBe("PROFESSOR");
  expect(lessonStep(PRODUCTION, PROFESSOR_ACCOUNT)).toEqual({ kind: "prove", account: PROFESSOR_ACCOUNT });
  const missing = lessonStep(PRODUCTION, null);
  expect(missing.kind).toBe("problem");
  expect(missing.kind === "problem" && missing.text).toContain(PROFESSOR_SECRETS);
  const preview = lessonStep(PREVIEW, PROFESSOR_ACCOUNT);
  expect(preview.kind).toBe("note");
  expect(preview.kind === "note" && preview.text).toContain(`never on ${PREVIEW}`);
  const researcher: User = { id: "e2e", email: "e2e@example.org", name: "E2E", role: "RESEARCHER" };
  const professor: User = { id: "e2e-professor", email: PROFESSOR_ACCOUNT.email, name: "E2E Professor", role: "PROFESSOR" };
  expect(canBuildLessons(researcher)).toBe(false);
  expect(professorProblems(professor)).toEqual([]);
  expect(professorProblems(researcher)).toEqual(["the Professor E2E account signed in as a Researcher, who may not build a lesson pack"]);
});

test("a lesson pack fails when it cites nothing or a source its explainer never streamed", () => {
  const source = (id: string): SourceRecord => ({ id, kind: "PAPER", title: id, publisher: null, year: null, doi: null, url: `https://example.org/${id}` });
  expect(lessonSourceProblems([source("a")], [source("a"), source("b")])).toEqual([]);
  expect(lessonSourceProblems([], [source("a")])).toEqual(["the lesson pack cites no source"]);
  expect(lessonSourceProblems([source("a"), source("c"), source("d")], [source("a")])).toEqual(["the lesson pack cites 2 sources the explainer does not"]);
});

test("a preview run's lesson note is listed under the exports, which still pass", () => {
  const note = lessonStep(PREVIEW, null);
  expect(note.kind).toBe("note");
  const text = note.kind === "note" ? note.text : "";
  const report: AnswersReport = {
    kind: "answers",
    baseUrl: PREVIEW,
    runId: "7",
    startedAt: "x",
    role: "RESEARCHER",
    problemCount: 0,
    unasked: [],
    questions: [],
    exports: { label: "English", explainerId: "e1", lessonExplainerId: null, files: ["a.pdf", "a.bib"], problems: [], notes: [text] }
  };
  const markdown = summaryMarkdown([report], { runId: null, baseUrl: null, startedAt: "x", questionsRequested: true });
  expect(markdown).toContain("### Exports\n\nFrom the English explainer: 2 files, Pass.");
  expect(markdown).toContain("- no lesson pack was built: The Professor and Admin accounts sign in only on");
});

const LEARNER_CAPABILITIES = ["ASK_STANDARD", "VOICE", "GENERATE_IMAGE", "SAVE_EXPORT"];
const SERVED_CAPABILITIES: Record<"STUDENT" | "RESEARCHER", string[]> = {
  STUDENT: LEARNER_CAPABILITIES,
  RESEARCHER: [...LEARNER_CAPABILITIES, "GENERATE_VIDEO", "READ_RESEARCHER_QUOTES", "PROPOSE_KNOWLEDGE", "RUN_ENRICHMENT", "ACCEPT_ALIASES"]
};

test("the production nav expectation for learners is what the client draws for them with the capabilities the server grants", () => {
  for (const role of ["STUDENT", "RESEARCHER"] as const satisfies readonly UserRole[]) {
    const user: User = { id: role, email: `${role}@example.org`, name: role, role, capabilities: SERVED_CAPABILITIES[role] };
    const shown = NAV_ITEMS.filter((item) => isNavItemVisible(item, user, false));
    expect(NAV_BY_ROLE[role]?.menu).toEqual(shown.map((item) => item.label));
    expect(NAV_BY_ROLE[role]?.bar).toEqual(shown.filter((item) => item.group === null).map((item) => item.label));
    expect(NAV_BY_ROLE[role]?.account).toEqual(shown.filter((item) => item.group !== null).map((item) => item.label));
  }
});
