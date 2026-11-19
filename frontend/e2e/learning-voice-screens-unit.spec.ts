import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { MyContributions } from "@/components/artisan/MyContributions";
import { LoadingPanel, RetryPanel } from "@/components/RemotePanels";
import { FieldTranscriptView } from "@/components/voices/FieldTranscriptView";
import type { FieldTranscript, TranscriptLine } from "@/lib/fieldVoicesContract";
import type { Contribution, ContributionList } from "@/lib/testimonyContract";

import { attribute, shownText } from "./explainerRender";

const AJRAKH = { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" };

function text(html: string): string {
  return shownText(html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " "));
}

function line(id: string, language: string, words: string): TranscriptLine {
  return { id, position: 1, speakerKey: "speaker_0", locator: "0:06–0:33", language, text: words, english: null, englishSource: null, quotable: true };
}

const TRANSCRIPT: FieldTranscript = {
  schemaVersion: 1,
  id: "b54cab0c-b7da-47d8-9da9-d9ef38d657c8",
  origin: "FIELD_REPOSITORY",
  publisher: "Field Repository",
  title: "Field interview, Ajrakh documentation visit, 14 March 2026",
  mediaType: "AUDIO",
  recordedAt: "2026-03-14T10:22:00+05:30",
  durationMs: 790000,
  crafts: [AJRAKH],
  workshop: "Ajrakh documentation visit",
  context: ["Recorded in Kachchh, Gujarat"],
  stage: null,
  speakers: [{ key: "speaker_0", label: "Asha Demo", role: "ARTISAN" }],
  lines: [line("gu-1", "gu", "અમે ફટકડીને આમલીના બીજ સાથે વાટીએ છીએ."), line("ur-1", "ur", "ہم پھٹکری پیستے ہیں"), line("en-1", "en", "We grind the alum.")],
  english: null,
  englishSource: null,
  sourceId: "1fc8e36a-6642-43d5-b4cd-ca1e3e532438",
  citation: "Asha Demo, interview recorded 14 March 2026, Ajrakh documentation visit, Field Repository, whole recording"
};

function contribution(overrides: Partial<Contribution>): Contribution {
  return {
    id: "c-1",
    status: "PENDING",
    conversationId: "v-1",
    craft: AJRAKH,
    discipline: "CHEMISTRY",
    claimText: null,
    quote: "ફટકડી રંગ પકડે છે.",
    language: "gu",
    english: "Alum holds the colour.",
    englishSource: "MACHINE",
    locator: "1:02",
    recordedAt: "2026-11-10T09:00:00Z",
    line: "Asha, Kachchh",
    submittedAt: "2026-11-11T09:00:00Z",
    reviewedAt: null,
    reviewerRole: null,
    rejectReason: null,
    reviewNote: null,
    approvedAt: null,
    withdrawnAt: null,
    ...overrides
  };
}

test("a field interview lists every field of its recording beside the transcript", () => {
  const html = renderToStaticMarkup(createElement(FieldTranscriptView, { transcript: TRANSCRIPT }));
  const shown = text(html);
  expect(shown).toContain("Length 13:10");
  expect(shown).toContain("Medium Sound recording");
  expect(shown).toContain("Published by Field Repository");
  expect(shown).toContain("Speakers Asha Demo, artisan");
  expect(shown).toContain("Workshop Ajrakh documentation visit");
  expect(shown).toContain("Transcript · 3 lines");
  expect(shown).toContain("Cite this recording");
  expect(html).toContain('href="/crafts/Kutch-Ajrakh"');
  expect(attribute(html, "fact-grid", "data-columns")).toEqual(["4"]);
});

test("each transcript line names its script, Urdu in Nastaliq and English with none", () => {
  const html = renderToStaticMarkup(createElement(FieldTranscriptView, { transcript: TRANSCRIPT }));
  expect(html).toMatch(/<p lang="gu" dir="auto" data-script="Gujr"/);
  expect(html).toMatch(/<p lang="ur" dir="auto" data-script="Aran"/);
  expect(html).toMatch(/<p lang="en" dir="auto" class=/);
});

test("an artisan's shared lines show the four counts, every review field and a way back", () => {
  const listed: ContributionList = {
    counts: { pending: 1, approved: 0, rejected: 1, withdrawn: 2 },
    items: [contribution({}), contribution({ id: "c-2", status: "REJECTED", reviewedAt: "2026-11-12T09:00:00Z", reviewerRole: "PROFESSOR", rejectReason: "MISHEARD" })]
  };
  const html = renderToStaticMarkup(createElement(MyContributions, { listed, onChanged: () => undefined }));
  const shown = text(html);
  expect(shown).toContain("Waiting 1");
  expect(shown).toContain("Not shown 1");
  expect(shown).toContain("Taken back 2");
  expect(shown).toContain("About Chemistry");
  expect(shown).toContain("by a professor");
  expect(shown).toContain("Why not shown Misheard");
  expect(html.match(/>Withdraw</g)).toHaveLength(1);
  expect(attribute(html, "contribution", "data-testid")).toHaveLength(2);
});

test("an artisan with nothing shared reads what the list is for, never a gap", () => {
  const html = renderToStaticMarkup(createElement(MyContributions, { listed: { counts: { pending: 0, approved: 0, rejected: 0, withdrawn: 0 }, items: [] }, onChanged: () => undefined }));
  expect(html).toContain('data-testid="empty-state"');
  expect(text(html)).not.toMatch(/nothing|not yet|no data|coming soon/i);
});

test("a view still opening is a sunk skeleton with a spoken label, and a failed one offers one retry", () => {
  const loading = renderToStaticMarkup(createElement(LoadingPanel, { label: "Opening your lessons" }));
  expect(loading).toContain('aria-busy="true"');
  expect(loading).toContain('<span class="sr-only">Opening your lessons</span>');
  expect(loading.replace(/<span class="sr-only">[^<]*<\/span>/, "")).not.toMatch(/Loading/);
  const failed = renderToStaticMarkup(createElement(RetryPanel, { message: "Couldn't load your lessons.", onRetry: () => undefined }));
  expect(failed).toContain('role="alert"');
  expect(failed.match(/<button/g)).toHaveLength(1);
  expect(text(failed)).toContain("Try again");
});
