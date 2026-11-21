import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthoredShell } from "../components/monograph/AuthoredShell";
import { BundleView, SlotRoot } from "../components/monograph/BundleView";
import { COMPONENT_VIEWS } from "../components/monograph/componentViews";
import { scopedBlocks } from "../components/monograph/DeferredShell";
import { heldCitation, SHELL_COMPLETE_EVENT, whenShellComplete } from "../components/monograph/kitGate";
import { deferredRest } from "../components/monograph/MonographPage";
import { ServerBundle, serverDrawn } from "../components/monograph/ServerBundle";
import { SERVER_VIEWS } from "../components/monograph/serverViews";
import { hashTargetMissing } from "../components/monograph/useShellTrigger";
import { bundleSources, KIT_CITES_ID } from "../lib/monographRenderKit";
import { componentBundles, pagePlan } from "../lib/monographRenderLayout";
import { checkedShellRest, documentDigest, documentTree, isChapter, lazyPictures, restAddress, shellParts, shellRest, shellRestPath } from "../lib/monographRenderShell";
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

test("the first chapter drawn on the server reads exactly as the client views draw it, and the server views are the registry's own", () => {
  const document = goldenDocument();
  const split = renderToStaticMarkup(createElement(AuthoredShell, { document, shell: document.shell ?? "", rest: shellRestPath(document.subjectSlug, document.version) }));
  const whole = renderToStaticMarkup(createElement(AuthoredShell, { document, shell: document.shell ?? "" }));
  const opening = '<section class="kv-ch" id="answer"';
  const lead = split.slice(split.indexOf(opening), split.indexOf('<div class="min-h-[300vh]"'));
  const first = whole.slice(whole.indexOf(opening), whole.indexOf('<section class="kv-ch" id="cloth"'));
  expect(lead.length).toBeGreaterThan(1000);
  expect(lead).toBe(first);
  for (const [kind, view] of Object.entries(SERVER_VIEWS)) expect(view, kind).toBe(COMPONENT_VIEWS[kind]);
});

test("a component of a server kind is drawn in the same slot markup as its client view draws", () => {
  const document = goldenDocument();
  const label = "shared/chemistry/indigo-reduction-player";
  const bundles = componentBundles(document, label);
  const set = { bundles, sources: bundleSources(document, bundles), bare: false };
  expect(serverDrawn(bundles, label)).toBe(true);
  const server = renderToStaticMarkup(createElement(ServerBundle, { label, set }));
  const root = { bundles, sources: set.sources, bare: false } as Parameters<typeof SlotRoot>[0];
  const client = renderToStaticMarkup(createElement(SlotRoot, root, createElement(BundleView, { label })));
  expect(server).toContain('class="kv-slot contents"');
  expect(server).toBe(client);
});

test("the rest carries its own bundles, every picture in it lazy, and the kit's data, for one version only", () => {
  const document = goldenDocument();
  const rest = shellRest(document);
  expect(rest.version).toBe(document.version);
  expect(rest.data.map((block) => block.id)).toContain(KIT_CITES_ID);
  expect(rest.data.find((block) => block.id === KIT_CITES_ID)?.scope).toBeNull();
  expect(rest.data.find((block) => block.id === "kv-data")?.scope).toBe("rm");
  expect(rest.data.find((block) => block.id === "rs-data")?.scope).toBe("pt");
  expect(scopedBlocks([{ id: "a", value: 1, scope: "rm" }, { id: "b", value: 2, scope: null }, { id: "c", value: 3, scope: "rm" }]).map(([scope, held]) => [scope, held.map((block) => block.id)])).toEqual([
    ["rm", ["a", "c"]],
    [null, ["b"]]
  ]);
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

test("an authored shell defers its rest only on a craft's page, at its own version and content's address", () => {
  const document = goldenDocument();
  const plan = pagePlan(document);
  expect(deferredRest(document, plan, true)).toBe(`/crafts/Kutch-Ajrakh/shell/v${document.version}-${documentDigest(document)}`);
  const grounded = { ...document, content: { ...document.content, data: { ...document.content.data, "why-here": { readings: 1 } } } };
  expect(deferredRest(grounded, plan, true)).not.toBe(deferredRest(document, plan, true));
  expect(restAddress(`v${document.version}-${documentDigest(document)}`)).toEqual({ version: document.version, digest: documentDigest(document), language: null });
  expect(deferredRest(document, plan, false)).toBeNull();
  expect(deferredRest({ ...document, subjectKind: "category" }, plan, true)).toBeNull();
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
