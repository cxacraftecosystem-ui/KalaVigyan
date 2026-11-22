import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ConfirmProvider } from "@/components/dialogs/ConfirmDialog";
import { NAV_ITEMS, isNavItemVisible } from "@/components/DynamicIslandNav";
import { CompareLinks, FollowUpBox, selfCheckOffered } from "@/components/learn/ExplainerFooter";
import { ExplainerActions, VersionPicker } from "@/components/learn/ExplainerTools";
import { NotesInbox, type NotesActions } from "@/components/learn/NotesInbox";
import { SavedList } from "@/components/learn/SavedList";
import { ApiError } from "@/lib/api";
import { compareSuggestions } from "@/lib/comparePage";
import { dispositionFileName, downloadApiFile } from "@/lib/download";
import type { Explainer } from "@/lib/explainerContract";
import { askingExplainer, emptyExplainer } from "@/lib/explainerState";
import { parseExplainerStreamBlock, type ExplainerEvent } from "@/lib/explainerStream";
import {
  explainerRef,
  explainerStateOf,
  followingExplainer,
  followUpRequest,
  knownVersions,
  reduceAnswerEvent,
  STALE_FOLLOW_UP,
  versionChanges,
  versionOptions,
  withDeepeningBlock
} from "@/lib/explainerVersions";
import { buildsOnShape, notificationListShape, savedExplainerListShape, explainerHistoryShape, explainerVersionDocumentShape, type BuildsOnEvent } from "@/lib/learningContract";
import { CITATION_FORMATS, LESSON_FORMATS } from "@/lib/lessonContract";
import { CITATION_FORMAT_LABEL, CITATION_FORMAT_ORDER, LESSON_FORMAT_LABEL, LESSON_FORMAT_ORDER } from "@/lib/lessonView";
import { digestChoice, explainerHref, newsText, notesCapText, NOTES_SHOWN_MAX, unreadText, updateFacets, updateHref } from "@/lib/savedView";
import { positiveParam } from "@/lib/searchParams";
import { parseShape } from "@/lib/shape";
import type { User, UserRole } from "@/lib/types";

import { attribute, shownText, withReading } from "./explainerRender";
import { readRepo } from "./phaseBFixture";

type Golden = Record<string, unknown>;

const golden = (name: string): Golden => JSON.parse(readRepo("shared", name)) as Golden;
const VERSIONS = golden("learning.versions.golden.json");
const ALERTS = golden("learning.alerts.golden.json");
const FIRST = golden("explainer.document.golden.json") as unknown as Explainer;
const HISTORY = parseShape(explainerHistoryShape, VERSIONS.history);
const LATEST = parseShape(explainerVersionDocumentShape, VERSIONS.latest);
const NOTES = parseShape(notificationListShape, ALERTS.notifications);
const SAVED = parseShape(savedExplainerListShape, ALERTS.saved);
const EXPLAINER_ID = "0c5e7a1d-2b3f-4c6d-8e9f-a0b1c2d3e4f5";
const FIRST_DOCUMENT = { schemaVersion: 1 as const, mark: HISTORY.versions[0], explainer: FIRST };
const person = (role: UserRole): User => ({ id: role, email: `${role}@example.org`, name: role, role });
const NO_ACTIONS: NotesActions = { busy: null, onUpdate: () => undefined, onRead: () => undefined };

function text(html: string): string {
  return shownText(html.replace(/<[^>]+>/g, ""));
}

function followUpEvents(): ExplainerEvent[] {
  const latest = LATEST.explainer;
  const section = (id: string) => latest.sections.find((held) => held.id === id)!;
  const block = (sectionId: string, blockId: string) => section(sectionId).blocks.find((held) => held.id === blockId)!;
  const s4 = section("s4");
  return [
    { type: "understood", data: latest.understood },
    { type: "builds_on", data: VERSIONS.buildsOn as BuildsOnEvent },
    { type: "section_started", data: { id: "s2", discipline: "GEOGRAPHY", title: "Why the water matters", order: 2, state: "RESEARCHING" } },
    { type: "block", data: { sectionId: "s2", block: block("s2", "s2.b2") } },
    { type: "section_done", data: { sectionId: "s2", state: "READY", searched: null } },
    { type: "section_started", data: { id: "s4", discipline: s4.discipline, title: s4.title, order: s4.order, state: "WRITING" } },
    { type: "block", data: { sectionId: "s4", block: block("s4", "s4.b1") } },
    { type: "section_done", data: { sectionId: "s4", state: "READY", searched: null } },
    { type: "version", data: LATEST.mark },
    { type: "done", data: { answerId: LATEST.mark.answerId } }
  ];
}

test("a stored version opens as a finished explainer that names itself", () => {
  const state = explainerStateOf(FIRST_DOCUMENT);
  expect(state.phase).toBe("done");
  expect(state.sections.map((section) => section.id)).toEqual(["s1", "s2", "s3"]);
  expect(explainerRef(state)).toEqual({ explainerId: EXPLAINER_ID, version: 1 });
  expect(explainerRef({ ...emptyExplainer(), phase: "done", answerId: EXPLAINER_ID })).toEqual({ explainerId: EXPLAINER_ID, version: 1 });
  expect(explainerRef(emptyExplainer())).toBeNull();
});

test("a follow-up keeps version 1 and builds the stored version 2 block for block", () => {
  const base = explainerStateOf(FIRST_DOCUMENT);
  const ref = explainerRef(base)!;
  const asking = followingExplainer(base, ref, LATEST.mark.question);
  expect(asking.sections.map((section) => section.id)).toEqual(["s1", "s2", "s3"]);
  expect(explainerRef(asking)).toEqual(ref);
  const built = followUpEvents().reduce(reduceAnswerEvent, asking);
  const expected = [
    ["s1", ["s1.b1", "s1.b2"]],
    ["s2", ["s2.b1", "s2.b2"]],
    ["s3", ["s3.b1"]],
    ["s4", ["s4.b1"]]
  ];
  expect(built.sections.map((section) => [section.id, section.blocks.map((block) => block.id)])).toEqual(expected);
  expect(built.sections.every((section) => section.state === "READY")).toBe(true);
  expect(built.mark).toEqual(LATEST.mark);
  expect(built.basedOn).toBeNull();
  expect(explainerRef(built)).toEqual({ explainerId: EXPLAINER_ID, version: 2 });
  expect(built.answerId).toBe("7a1c3e5f-2b4d-4f6a-8c9e-0b1d3f5a7c9e");
});

test("a deepening block goes before the section's pictures, and a stale base fails loudly", () => {
  const [ladder, pictures] = FIRST.sections[0].blocks;
  const prose = LATEST.explainer.sections[1].blocks[1];
  expect(withDeepeningBlock([ladder, pictures], prose).map((block) => block.id)).toEqual(["s1.b1", "s2.b2", "s1.b2"]);
  expect(withDeepeningBlock([ladder], prose).map((block) => block.id)).toEqual(["s1.b1", "s2.b2"]);
  expect(withDeepeningBlock([ladder, prose], prose)).toHaveLength(2);
  const base = explainerStateOf(FIRST_DOCUMENT);
  const asking = followingExplainer(base, { explainerId: EXPLAINER_ID, version: 1 }, "Why?");
  const stale = reduceAnswerEvent(asking, { type: "builds_on", data: { ...(VERSIONS.buildsOn as BuildsOnEvent), version: 3 } });
  expect(stale.phase).toBe("failed");
  expect(stale.error).toBe(STALE_FOLLOW_UP);
  const nothingNew: ExplainerEvent[] = [
    { type: "section_started", data: { id: "s2", discipline: "GEOGRAPHY", title: "Why the water matters", order: 2, state: "RESEARCHING" } },
    { type: "section_done", data: { sectionId: "s2", state: "EMPTY", searched: "Khamir" } },
    { type: "section_started", data: { id: "s4", discipline: "HISTORY", title: "History", order: 4, state: "RESEARCHING" } },
    { type: "section_done", data: { sectionId: "s4", state: "EMPTY", searched: "Khamir" } },
    { type: "done", data: { answerId: null } }
  ];
  const settled = nothingNew.reduce(reduceAnswerEvent, asking);
  expect(settled.sections.map((section) => [section.id, section.state, section.blocks.length])).toEqual([
    ["s1", "READY", 2],
    ["s2", "READY", 1],
    ["s3", "READY", 1],
    ["s4", "EMPTY", 0]
  ]);
  expect(explainerRef(settled)).toEqual({ explainerId: EXPLAINER_ID, version: 1 });
});

test("Check yourself asks for a quiz only when the finished stream did not say there is none", () => {
  const finished = (frame: string) => reduceAnswerEvent(askingExplainer("Why is ajrakh blue?", "en"), parseExplainerStreamBlock(frame)!);
  const offered = finished(`event: done\ndata: {"answerId":"${EXPLAINER_ID}","quizAvailable":true}`);
  const none = finished(`event: done\ndata: {"answerId":"${EXPLAINER_ID}","quizAvailable":false}`);
  const unknown = finished(`event: done\ndata: {"answerId":"${EXPLAINER_ID}"}`);
  expect([offered.quizAvailable, none.quizAvailable, unknown.quizAvailable]).toEqual([true, false, null]);
  expect([selfCheckOffered(offered), selfCheckOffered(none), selfCheckOffered(unknown)]).toEqual([true, false, true]);
  expect(selfCheckOffered({ ...offered, answerId: null })).toBe(false);
  expect(selfCheckOffered(explainerStateOf(FIRST_DOCUMENT))).toBe(true);
  expect(followingExplainer(none, { explainerId: EXPLAINER_ID, version: 1 }, "Why?").quizAvailable).toBeNull();
});

test("an added section that found nothing shows what was searched until the version is stored, which leaves it out", () => {
  const base = explainerStateOf(FIRST_DOCUMENT);
  const asking = followingExplainer(base, { explainerId: EXPLAINER_ID, version: 1 }, LATEST.mark.question);
  const [understood, buildsOn, ...rest] = followUpEvents();
  const version = rest.find((event) => event.type === "version")!;
  const searching: ExplainerEvent[] = [
    understood,
    buildsOn,
    ...rest.filter((event) => event.type !== "version" && event.type !== "done"),
    { type: "section_started", data: { id: "s5", discipline: "HISTORY", title: "History", order: 5, state: "RESEARCHING" } },
    { type: "section_done", data: { sectionId: "s5", state: "EMPTY", searched: "Khamir" } }
  ];
  const moment = searching.reduce(reduceAnswerEvent, asking);
  expect(moment.sections.map((section) => [section.id, section.state, section.searched])).toContainEqual(["s5", "EMPTY", "Khamir"]);
  const stored = reduceAnswerEvent(moment, version);
  expect(stored.sections.map((section) => section.id)).toEqual(LATEST.explainer.sections.map((section) => section.id));
  expect(stored.sections.map((section) => section.id)).toEqual(["s1", "s2", "s3", "s4"]);
  expect(stored.sections.some((section) => "added" in section)).toBe(false);
});

test("the follow-up request carries only the question and what it builds on", () => {
  const request = followUpRequest({ explainerId: EXPLAINER_ID, version: 1 }, "  Why did water push Ajrakh printers?  ");
  expect(request).toEqual({ question: "Why did water push Ajrakh printers?", depth: null, buildsOn: VERSIONS.request });
  expect(parseShape(buildsOnShape, request.buildsOn)).toEqual(VERSIONS.request);
  expect(followUpRequest({ explainerId: EXPLAINER_ID, version: 2 }, "q", ["GEOGRAPHY", "HISTORY"]).buildsOn?.facets).toEqual(["GEOGRAPHY", "HISTORY"]);
});

test("the stream reads builds_on and version events", () => {
  const builds = parseExplainerStreamBlock(`event: builds_on\ndata: ${JSON.stringify(VERSIONS.buildsOn)}`);
  expect(builds?.type).toBe("builds_on");
  const version = parseExplainerStreamBlock(`event: version\ndata: ${JSON.stringify(LATEST.mark)}`);
  expect(version).toEqual({ type: "version", data: LATEST.mark });
});

test("versions list newest first and say what each one changed", () => {
  const versions = knownVersions(HISTORY.versions, LATEST.mark);
  expect(versions.map((mark) => mark.version)).toEqual([1, 2]);
  expect(knownVersions([], LATEST.mark).map((mark) => mark.version)).toEqual([2]);
  expect(knownVersions([HISTORY.versions[0]], LATEST.mark).map((mark) => mark.version)).toEqual([1, 2]);
  expect(versionOptions(versions).map((option) => option.label)).toEqual(["Version 2 · latest", "Version 1"]);
  expect(versionOptions(versions)[0].hint).toBe("Why did water push Ajrakh printers from Dhamadka to Ajrakhpur?");
  expect(versionChanges(LATEST.mark, LATEST.explainer.sections)).toEqual(["Deepened Why the water matters", "Added History"]);
});

test("the version picker shows only with two versions, with the changes and a way back to the latest", () => {
  const onPick = () => undefined;
  const sections = explainerStateOf(LATEST).sections;
  expect(withReading(createElement(VersionPicker, { choice: { versions: [HISTORY.versions[0]], viewing: HISTORY.versions[0], onPick }, sections }))).toBe("");
  const latest = withReading(createElement(VersionPicker, { choice: { versions: HISTORY.versions, viewing: LATEST.mark, onPick }, sections }));
  expect(text(latest)).toContain("Deepened Why the water matters · Added History");
  expect(latest).not.toContain('data-testid="version-latest"');
  const older = withReading(createElement(VersionPicker, { choice: { versions: HISTORY.versions, viewing: HISTORY.versions[0], onPick }, sections }));
  expect(older).toContain('data-testid="version-latest"');
  expect(older).not.toContain('data-testid="version-changes"');
});

test("every role can save and export; lessons are offered to professors and above", () => {
  const ref = { explainerId: EXPLAINER_ID, version: 2 };
  const student = renderToStaticMarkup(createElement(ConfirmProvider, null, createElement(ExplainerActions, { explainer: ref, user: person("STUDENT") })));
  expect(student).toContain('data-testid="save-explainer"');
  expect(student).toContain('data-testid="explainer-export"');
  expect(student).not.toContain('data-testid="make-lesson"');
  const professor = renderToStaticMarkup(createElement(ConfirmProvider, null, createElement(ExplainerActions, { explainer: ref, user: person("PROFESSOR") })));
  expect(attribute(professor, "make-lesson", "href")).toEqual([`/lessons/new?explainer=${EXPLAINER_ID}&amp;version=2`]);
  expect(renderToStaticMarkup(createElement(ExplainerActions, { explainer: ref, user: null }))).toBe("");
});

test("the follow-up box asks only once there is a question, and compare is offered for the candidates", () => {
  const box = renderToStaticMarkup(createElement(FollowUpBox, { onAsk: () => undefined }));
  expect(box).toContain('for="follow-up-question"');
  expect(box).toMatch(/<button type="submit"[^>]*disabled=""/);
  const ajrakh = { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" };
  const bagru = { slug: "Bagru-Hand-Block-Print", name: "Bagru Hand Block Print", path: "/crafts/Bagru-Hand-Block-Print" };
  expect(compareSuggestions([ajrakh], [bagru])).toEqual([{ label: "Compare with Bagru Hand Block Print", href: "/compare?crafts=Kutch-Ajrakh&crafts=Bagru-Hand-Block-Print" }]);
  expect(compareSuggestions([ajrakh, bagru], [])).toEqual([{ label: "Compare Kutch Ajrakh and Bagru Hand Block Print", href: "/compare?crafts=Kutch-Ajrakh&crafts=Bagru-Hand-Block-Print" }]);
  expect(compareSuggestions([ajrakh], [ajrakh])).toEqual([]);
  expect(compareSuggestions([], [bagru])).toEqual([]);
  const links = renderToStaticMarkup(createElement(CompareLinks, { understood: LATEST.explainer.understood }));
  expect(text(links)).toContain("Compare with Bagru Hand Block Print");
});

test("a note says what got better, links to its explainer and offers the update", () => {
  const [note] = NOTES.items;
  expect(newsText(note.payload.news)).toBe("3 new findings in Geography and water · 1 in History");
  expect(newsText([{ facet: "HISTORY", newClaims: 1 }])).toBe("1 new finding in History");
  expect(updateHref(note)).toBe(`/ask?explainer=${EXPLAINER_ID}&update=GEOGRAPHY%2CHISTORY`);
  expect(updateFacets(new URLSearchParams(updateHref(note).split("?")[1]).get("update"))).toEqual(["GEOGRAPHY", "HISTORY"]);
  expect(updateFacets("HISTORY,BOGUS,HISTORY, CLIMATE")).toEqual(["HISTORY", "CLIMATE"]);
  expect(updateFacets(null)).toEqual([]);
  expect(unreadText(NOTES.unread)).toBe("1 new note");
  expect(unreadText(0)).toBeNull();
  expect(NOTES_SHOWN_MAX).toBe(Number(/NOTIFICATIONS_SHOWN_MAX = (\d+)/.exec(readRepo("backend", "app", "research", "alerts.py"))?.[1]));
  expect([notesCapText(49), notesCapText(50)]).toEqual([null, "Showing the latest 50."]);
  const html = withReading(createElement(NotesInbox, { notes: NOTES.items, actions: NO_ACTIONS }));
  expect(text(html)).toContain("This answer got better");
  expect(attribute(html, "note", "data-unread")).toEqual(["true"]);
  expect(html).toContain('data-testid="note-update"');
  expect(html).toContain('data-testid="note-read"');
  expect(html).toContain(`href="${explainerHref(EXPLAINER_ID)}"`);
  const read = withReading(createElement(NotesInbox, { notes: [{ ...note, readAt: "2026-11-19T08:00:00Z" }], actions: NO_ACTIONS }));
  expect(attribute(read, "note", "data-unread")).toEqual(["false"]);
  expect(read).not.toContain('data-testid="note-read"');
  const empty = text(withReading(createElement(NotesInbox, { notes: [], actions: NO_ACTIONS })));
  expect(empty).toContain("Notes on your saved answers");
  expect(empty).not.toMatch(/nothing|yet/i);
});

test("notes are drawn finished at first paint and take no motion setting", () => {
  const html = withReading(createElement(NotesInbox, { notes: NOTES.items, actions: NO_ACTIONS }));
  expect(html).not.toMatch(/translateY|opacity:\s*0/);
  expect(readRepo("frontend", "components", "learn", "NotesInbox.tsx")).not.toMatch(/reduce/);
});

test("saved answers list their version, mark a newer one and say when there are none", () => {
  const [saved] = SAVED.items;
  const html = renderToStaticMarkup(createElement(SavedList, { items: SAVED.items, busy: null, onRemove: () => undefined }));
  expect(text(html)).toContain(saved.question);
  expect(text(html)).toContain("Version 2");
  expect(html).not.toContain('data-testid="saved-newer"');
  const newer = renderToStaticMarkup(createElement(SavedList, { items: [{ ...saved, seenVersion: 1 }], busy: null, onRemove: () => undefined }));
  expect(newer).toContain('data-testid="saved-newer"');
  const none = renderToStaticMarkup(createElement(SavedList, { items: [], busy: null, onRemove: () => undefined }));
  expect(text(none)).toContain("Your saved answers");
  expect(text(none)).not.toMatch(/nothing|yet/i);
  expect(none).toContain('href="/ask"');
});

test("the file name comes from the server's Content-Disposition, and a file with none is refused", async () => {
  expect(dispositionFileName(`attachment; filename="KalaVigyan_Explainer_Report_v2.pdf"; filename*=UTF-8''KalaVigyan_%E0%A4%85_v2.pdf`)).toBe("KalaVigyan_अ_v2.pdf");
  expect(dispositionFileName(`attachment; filename="KalaVigyan_Lesson_Slides.pptx"`)).toBe("KalaVigyan_Lesson_Slides.pptx");
  expect(dispositionFileName(`attachment; filename*=UTF-8''%E0%A4; filename="Plain.bib"`)).toBe("Plain.bib");
  expect(dispositionFileName("attachment")).toBeNull();
  expect(dispositionFileName(null)).toBeNull();
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response("x", { status: 200 });
    await expect(downloadApiFile("/lessons/x/files/pdf", "Nope.")).rejects.toMatchObject({ status: 502, message: "Nope." });
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Not yours." }), { status: 404, headers: { "content-type": "application/json" } });
    const refused = await downloadApiFile("/lessons/x/files/pdf", "Nope.").catch((error: unknown) => error);
    expect(refused).toBeInstanceOf(ApiError);
    expect((refused as ApiError).message).toBe("Not yours.");
  } finally {
    globalThis.fetch = original;
  }
});

test("every export format the contract names has one label, in one order", () => {
  expect([...CITATION_FORMAT_ORDER].sort()).toEqual([...CITATION_FORMATS].sort());
  expect([...LESSON_FORMAT_ORDER].sort()).toEqual([...LESSON_FORMATS].sort());
  expect(CITATION_FORMAT_ORDER.map((format) => CITATION_FORMAT_LABEL[format])).toEqual(["APA", "BibTeX", "RIS", "CSL-JSON"]);
  expect(LESSON_FORMAT_ORDER.map((format) => LESSON_FORMAT_LABEL[format])).toEqual(["Slides · PPTX", "Handout · PDF", "Web slides · HTML"]);
});

test("Saved is everyone's and Lessons only a professor's in the navigation, and addresses parse strictly", () => {
  const saved = NAV_ITEMS.find((item) => item.href === "/saved")!;
  const lessons = NAV_ITEMS.find((item) => item.href === "/lessons")!;
  expect(isNavItemVisible(saved, person("STUDENT"), false)).toBe(true);
  expect(["STUDENT", "RESEARCHER", "PROFESSOR", "ADMIN", "MASTER_ADMIN"].map((role) => isNavItemVisible(lessons, person(role as UserRole), false))).toEqual([false, false, true, true, true]);
  expect(explainerHref(EXPLAINER_ID, 1)).toBe(`/ask?explainer=${EXPLAINER_ID}&version=1`);
  expect([positiveParam("2"), positiveParam("0"), positiveParam("-1"), positiveParam("2x"), positiveParam(null)]).toEqual([2, null, null, null, null]);
});

test("the weekly email switch is drawn only while the server offers the digest", () => {
  expect(digestChoice({ theme: "system", alertDigest: true, alertDigestOffered: true })).toEqual({ offered: true, on: true });
  expect(digestChoice({ alertDigest: true, alertDigestOffered: false })).toEqual({ offered: false, on: true });
  expect(digestChoice({ theme: "dark" })).toEqual({ offered: false, on: false });
  expect(digestChoice(null)).toEqual({ offered: false, on: false });
});
