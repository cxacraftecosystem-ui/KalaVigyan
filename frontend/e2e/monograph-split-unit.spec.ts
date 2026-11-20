import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthoredShell } from "../components/monograph/AuthoredShell";
import { heldCitation, SHELL_COMPLETE_EVENT, whenShellComplete } from "../components/monograph/kitGate";
import { deferredRest } from "../components/monograph/MonographPage";
import { hashTargetMissing } from "../components/monograph/useShellTrigger";
import { KIT_CITES_ID } from "../lib/monographRenderKit";
import { checkedShellRest, documentTree, isChapter, lazyPictures, shellParts, shellRest, shellRestPath } from "../lib/monographRenderShell";
import { shellSlots } from "../lib/monographShellTree";

import { goldenDocument } from "./monographNative";

const chapterIds = (html: string) => [...html.matchAll(/<section class="kv-ch" id="([a-z-]+)"/g)].map((found) => found[1]);

test("the lead of a split monograph is its first chapter, and lead and rest together are the whole shell", () => {
  const document = goldenDocument();
  const whole = documentTree(document);
  const { lead, rest } = shellParts(document);
  expect(lead.tree.filter(isChapter)).toHaveLength(1);
  expect([...lead.tree, ...rest.tree]).toEqual(whole);
  expect(whole.filter(isChapter).length).toBeGreaterThan(10);
  expect([...shellSlots(lead.tree), ...shellSlots(rest.tree)].sort()).toEqual(shellSlots(whole).sort());
  for (const label of shellSlots(lead.tree)) expect(Object.hasOwn(lead.bundles, label), label).toBe(true);
  for (const label of shellSlots(rest.tree)) expect(Object.hasOwn(rest.bundles, label), label).toBe(true);
});

test("the page draws only its first chapter and a reserved place for the rest, and the whole shell when nothing is deferred", () => {
  const document = goldenDocument();
  const split = renderToStaticMarkup(createElement(AuthoredShell, { document, shell: document.shell ?? "", rest: shellRestPath(document.subjectSlug, document.version) }));
  const whole = renderToStaticMarkup(createElement(AuthoredShell, { document, shell: document.shell ?? "" }));
  expect(chapterIds(split)).toEqual(["answer"]);
  expect(split).toContain('data-kv-deferred=""');
  expect(chapterIds(whole).length).toBeGreaterThan(10);
  expect(whole).not.toContain("data-kv-deferred");
  expect(split.length * 5).toBeLessThan(whole.length);
});

test("the rest carries its own bundles, every picture in it lazy, and the kit's data, for one version only", () => {
  const document = goldenDocument();
  const rest = shellRest(document);
  expect(rest.version).toBe(document.version);
  expect(rest.data.map((block) => block.id)).toContain(KIT_CITES_ID);
  const pictures = JSON.stringify(rest.bundles).match(/"loading":"[a-z]+"/g) ?? [];
  expect(pictures.length).toBeGreaterThan(0);
  expect(new Set(pictures)).toEqual(new Set(['"loading":"lazy"']));
  expect(JSON.stringify(rest.bundles)).not.toContain('"fetchPriority":"high"');
  expect(checkedShellRest(JSON.parse(JSON.stringify(rest)), document.version).tree).toEqual(rest.tree);
  expect(() => checkedShellRest(JSON.parse(JSON.stringify(rest)), document.version + 1)).toThrow(/another shape/);
  expect(lazyPictures({ picture: { src: "/a.jpg", width: 1, height: 1, alt: "A", loading: "eager", fetchPriority: "high" }, n: 2 })).toEqual({
    picture: { src: "/a.jpg", width: 1, height: 1, alt: "A", loading: "lazy", fetchPriority: null },
    n: 2
  });
});

test("only a published craft with an authored shell defers its rest, at its own version's address", () => {
  const document = goldenDocument();
  expect(deferredRest(document, true)).toBe(`/crafts/Kutch-Ajrakh/shell/v${document.version}`);
  expect(deferredRest(document, false)).toBeNull();
  expect(deferredRest({ ...document, shell: null }, true)).toBeNull();
  expect(deferredRest({ ...document, subjectKind: "category" }, true)).toBeNull();
});

test("the kit waits for a deferred rest, starts at once without one, and replays a citation pressed before it bound", () => {
  const view = new EventTarget() as unknown as Window;
  const waiting = { querySelector: () => ({}) } as unknown as ParentNode;
  const complete = { querySelector: () => null } as unknown as ParentNode;
  const starts: string[] = [];
  whenShellComplete(() => starts.push("at once"), view, complete);
  whenShellComplete(() => starts.push("after the rest"), view, waiting);
  expect(starts).toEqual(["at once"]);
  view.dispatchEvent(new Event(SHELL_COMPLETE_EVENT));
  expect(starts).toEqual(["at once", "after the rest"]);
  const handlers = new Map<string, (event: Event) => void>();
  const clicks = { addEventListener: (name: string, handler: (event: Event) => void) => handlers.set(name, handler), removeEventListener: (name: string) => handlers.delete(name) } as unknown as Window;
  let bound = false;
  const held = heldCitation(clicks, () => bound);
  const citation = { id: "cite-1" } as unknown as HTMLElement;
  const press = (target: unknown) => handlers.get("click")?.({ target } as unknown as Event);
  press({ closest: (selector: string) => (selector === ".kcite" ? citation : null) });
  press({ closest: () => null });
  expect(held.taken()).toBe(citation);
  expect(held.taken()).toBeNull();
  bound = true;
  press({ closest: () => citation });
  expect(held.taken()).toBeNull();
  held.stop();
  expect(handlers.has("click")).toBe(false);
});

test("a link to a chapter not yet drawn asks for the rest", () => {
  const root = { getElementById: (id: string) => (id === "answer" ? {} : null) } as unknown as Document;
  expect(hashTargetMissing("#chemistry", root)).toBe(true);
  expect(hashTargetMissing("#answer", root)).toBe(false);
  expect(hashTargetMissing("", root)).toBe(false);
});
