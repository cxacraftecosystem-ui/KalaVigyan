import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthProvider } from "../components/AuthProvider";
import { ComponentSlot, slotDrawing } from "../components/monograph/ComponentSlot";
import { KitShellTail } from "../components/monograph/KitShellTail";
import { MonographMasthead } from "../components/monograph/MonographMasthead";
import { MonographChapter, MonographPage } from "../components/monograph/MonographPage";
import { toolPatch } from "../components/monograph/ReaderSettings";
import { SourceList } from "../components/monograph/SourceList";
import { ThemeProvider } from "../components/ThemeProvider";
import { pagePlan } from "../lib/monographRenderLayout";

import { ASK, fixtureDocument, LIST, PICTURE, QUIZ } from "./monographFixture";

const markup = (element: ReactElement) => renderToStaticMarkup(element);
const provided = (element: ReactElement) => markup(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));

test("a component with a spec and a registered view is drawn natively, any other from its fragment", () => {
  const document = fixtureDocument();
  expect([PICTURE, QUIZ, LIST, ASK, "test-craft/overview/nothing"].map((label) => slotDrawing(document, label))).toEqual(["fragment", "view", "fragment", "view", "none"]);
  document.content.components[1] = { ...document.content.components[1], kind: "prose" };
  expect(slotDrawing(document, QUIZ)).toBe("none");
});

test("a view whose spec names a unit the document does not hold is not drawn, so a stale document never breaks the page", () => {
  const document = fixtureDocument();
  const named = JSON.stringify(document.specs[QUIZ]).match(/"(u\d{4})"/)?.[1] ?? "";
  document.content.units = Object.fromEntries(Object.entries(document.content.units).filter(([ref]) => ref !== named));
  expect(named).not.toBe("");
  expect(slotDrawing(document, QUIZ)).toBe("none");
  expect(markup(createElement(ComponentSlot, { document, label: QUIZ }))).toBe("");
});

test("a fragment is drawn as written inside a slot container React never re-renders", () => {
  const html = markup(createElement(ComponentSlot, { document: fixtureDocument(), label: PICTURE, scoped: false }));
  expect(html).toBe(
    '<div class="kv-slot contents" id="kv-slot-test-craft__design__cloth-photo" data-component="test-craft/design/cloth-photo">' +
      '<figure class="plate" id="photo"><img src="/x.jpg" alt="A cloth"><figcaption><p class="credit">Photo: test</p></figcaption></figure></div>'
  );
});

test("a fragment on a page sits in its scope, its last frame holding the markup", () => {
  const html = markup(createElement(ComponentSlot, { document: fixtureDocument(), label: PICTURE }));
  expect(html).toBe(
    `<div class="bx bx-pt my-12" data-component="${PICTURE}" data-component-kind="picture_plate" data-home="kind"><div class="screen"><div class="wrap kv-passage"><div class="spread">` +
      '<div class="main" id="kv-slot-test-craft__design__cloth-photo"><figure class="plate" id="photo"><img src="/x.jpg" alt="A cloth"><figcaption><p class="credit">Photo: test</p></figcaption></figure></div></div></div></div></div>'
  );
});

test("a fragment keeps the slot of the component placed inside it for its native view", () => {
  const html = markup(createElement(ComponentSlot, { document: fixtureDocument(), label: LIST }));
  expect(html).toContain(`<kv-slot component="${ASK}"></kv-slot>`);
  expect(html).not.toContain("asknext");
});

test("the quiz's native view draws its first question from the spec with the page's units", () => {
  const html = markup(createElement(ComponentSlot, { document: fixtureDocument(), label: QUIZ }));
  expect(html).toContain(`data-component="${QUIZ}" data-component-kind="quiz" data-home="kind"`);
  expect(html).not.toContain("data-kind=");
  expect(html).toContain('<div class="bx bx-rm" data-native-view="">');
  expect(html).toContain("<h3>Check yourself</h3>");
  expect(html).toContain("Question 1 of 1");
  expect(html).toContain("The cloth is printed twice before the");
  expect(html).toContain('aria-label="Source 1"');
  expect(html.match(/class="quiz-opt"/g)).toHaveLength(2);
});

test("a chapter draws its head in the spread: rail numeral, kicker, title, lede and margin notes", () => {
  const document = fixtureDocument();
  const html = markup(createElement(MonographChapter, { document, chapter: pagePlan(document).chapters[1], masthead: null }));
  expect(html.startsWith('<section class="kv-ch" id="made" data-ch="1" data-label="How it is made" aria-label="How it is made">')).toBe(true);
  expect(html).toContain('<div class="spread railed sec-head"><div class="rail"><span class="numeral">1</span></div>');
  expect(html).toContain('<p class="chapter-no in-main">1</p><p class="kicker sec-kicker">How it is made</p><h2 class="t-h2" id="made-h">Printed, then dyed</h2>');
  expect(html).toContain('<aside class="margin note" aria-label="Sources in this passage"><ul><li data-g="g1"><b>1</b><span>Test journal, 2023</span></li></ul></aside>');
  expect(html).toContain('<ul class="kv-list"><li>Scour the cloth</li><li>Print the resist</li></ul>');
});

test("the masthead names the subject once, with its kickers, cited lede, provenance and picture", () => {
  const document = fixtureDocument();
  const html = markup(createElement(MonographMasthead, { document, masthead: pagePlan(document).masthead }));
  expect(html.match(/<h1/g)).toHaveLength(1);
  expect(html).toContain('<p class="kicker kv-open-k"><span>Monograph</span></p><h1 class="kv-q">Test Craft</h1>');
  expect(html).toContain('<p class="kicker">The short answer</p><p class="t-lede ans-lede">');
  expect(html).toContain('<span class="kv-prov-n">Drawn from 2 sources</span>');
  expect(html).toContain('aria-label="Reliability of the 2 sources: 1 graded A, 1 graded B"');
  expect(html).toContain('id="kv-slot-test-craft__design__cloth-photo"');
});

test("the sources chapter lists each cited source with its byline, grade, support and link", () => {
  const html = markup(createElement(SourceList, { document: fixtureDocument() }));
  expect(html.match(/class="kv-src-li"/g)).toHaveLength(2);
  expect(html).toContain('<button type="button" class="src" data-g="g1" aria-pressed="false"><b>1</b>');
  expect(html).toContain("<span>Test Registry, 2023</span>");
  expect(html).toContain("A · peer-reviewed or official");
  expect(html).toContain("Supports 2 sentences here");
  expect(html).toContain("Supports 1 sentence here");
  expect(html.match(/Open the source/g)).toHaveLength(1);
});

test("the kit's shell tail carries the popover, the player and each data block in the scope its script reads", () => {
  const html = markup(createElement(KitShellTail, { document: fixtureDocument() }));
  expect(html).toContain('<div class="pop" id="kv-pop" role="dialog" aria-labelledby="kv-pop-t" hidden="">');
  expect(html).toContain('id="kv-player"');
  expect(html).toMatch(/<div class="bx bx-rm" hidden="">(<button[^>]*><\/button>){6}<script type="application\/json" id="kv-data">/);
  expect(html).toContain('<script type="application/json" id="loose-data">{"note":"\\u003c/script>"}</script>');
  expect(html).toContain('<script type="application/json" id="kv-cites">');
});

test("the whole page draws one h1, the rail of chapters with their numerals and the reader's display tools", () => {
  const html = provided(createElement(MonographPage, { document: fixtureDocument() }));
  expect(html.match(/<h1/g)).toHaveLength(1);
  expect(html).toContain('<a href="#answer" aria-current="location"><span>Answer</span></a>');
  expect(html).toContain('<a href="#made"><b>1</b><span>How it is made</span></a>');
  expect(html).toContain('<a href="#sources"><b>2</b><span>Sources</span></a>');
  expect([...html.matchAll(/<section class="kv-ch" id="([a-z-]+)"/g)].map((found) => found[1])).toEqual(["answer", "made", "sources"]);
  expect(html.match(/class="kv-tool"/g)).toHaveLength(4);
  expect(html).not.toContain("data-kv-tool");
});

test("the display tools change the app's own settings", () => {
  expect(toolPatch("theme", true)).toEqual({ theme: "light" });
  expect(toolPatch("theme", false)).toEqual({ theme: "dark" });
  expect(toolPatch("highContrast", false)).toEqual({ highContrast: "high" });
  expect(toolPatch("highContrast", true)).toEqual({ highContrast: "standard" });
  expect(toolPatch("reducedMotion", true)).toEqual({ reducedMotion: false });
});
