import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { VIEWS } from "../components/monograph/kinds/science";
import { NestedComponents } from "../components/monograph/NestedComponents";
import { SCIENCE_KINDS, SPEC_SHAPES_SCIENCE, type ScienceKind } from "../lib/componentSpecsScience";
import { svgNodeShape } from "../lib/componentSpecsScienceParts";
import type { MonographComponent, MonographContent } from "../lib/monographDocument";
import { parseShape, ShapeError } from "../lib/shape";
import { AJRAKH_DIR, fragmentFile, subtrees, tokenize, type Open, type Token } from "./monographMarkup";

const content = JSON.parse(readFileSync(join(AJRAKH_DIR, "content.json"), "utf8")) as MonographContent;
const byLabel = new Map(content.components.map((component) => [component.label, component]));

function view(label: string): ReactNode {
  const component = byLabel.get(label) as MonographComponent;
  const spec = JSON.parse(readFileSync(join(AJRAKH_DIR, "specs", `${label.replaceAll("/", "__")}.json`), "utf8"));
  return createElement(VIEWS[component.kind]!, { component, spec, unitRefs: [], renderUnit: (ref: string) => createElement("kv-slot", { unit: ref }), renderComponent: (label: string) => createElement("kv-component", { label }) });
}

const placeholder = (label: string) => createElement("kv-component", { label });

function drawn(label: string, nested: (label: string) => ReactNode = placeholder): Token[] {
  return tokenize(renderToStaticMarkup(createElement(NestedComponents.Provider, { value: nested }, view(label))));
}

function all(tokens: Token[], tag: string, name?: string): Open[] {
  return tokens.filter((token): token is Open => token.kind === "open" && token.tag === tag && (!name || (token.attrs.class ?? "").split(" ").includes(name)));
}

function texts(tokens: Token[], tag: string, name?: string): string[] {
  return subtrees(tokens, (open) => open.tag === tag && (!name || (open.attrs.class ?? "").split(" ").includes(name))).map(([from, to]) =>
    tokens.slice(from, to).map((token) => (token.kind === "text" ? token.text : "")).join("")
  );
}

const NUMBERED = /^\d+ /;
const STEPPED = ["kutch-ajrakh/chemistry/red-alum-madder-player", "kutch-ajrakh/chemistry/iron-tannin-black-player", "kutch-ajrakh/chemistry/white-resist-player", "shared/chemistry/indigo-reduction-player", "kutch-ajrakh/process/cloth-after-each-stage"];

function namedButtons(tokens: Token[]): { name: string; shown: string[] }[] {
  return subtrees(tokens, (open) => open.tag === "button" && NUMBERED.test(open.attrs["aria-label"] ?? "")).map(([from, to]) => ({
    name: (tokens[from] as Open).attrs["aria-label"] ?? "",
    shown: tokens.slice(from, to).flatMap((token) => (token.kind === "text" ? token.text.split(/\s+/) : [])).filter(Boolean)
  }));
}

test("each step and stage button is named by the words it shows, in the native view and the approved fragment alike", () => {
  for (const label of STEPPED) {
    const native = namedButtons(drawn(label));
    const approved = namedButtons(tokenize(readFileSync(fragmentFile(label), "utf8")));
    expect(native.length, label).toBeGreaterThan(0);
    expect(native, label).toEqual(approved);
    for (const button of native) expect(button.name.split(" "), label).toEqual(button.shown);
  }
});

test("a reaction player rests on its step, presses it on the rail and links its species to PubChem", () => {
  const red = drawn("kutch-ajrakh/chemistry/red-alum-madder-player");
  expect(all(red, "figure")[0].attrs).toMatchObject({ class: "rp", id: "rp-red", "data-track": "red", "data-step": "5", "data-steps": "5" });
  const rail = all(red, "button").filter((button) => NUMBERED.test(button.attrs["aria-label"] ?? ""));
  expect(rail.map((button) => button.attrs["aria-label"])).toEqual(["1 Tannin first", "2 The mordant", "3 Keep lime away", "4 The madder bath", "5 The lake"]);
  expect(rail.map((button) => button.attrs["aria-pressed"])).toEqual(["false", "false", "false", "false", "true"]);
  expect(all(red, "section", "rp-step").map((section) => "hidden" in section.attrs)).toEqual([true, true, true, true, false]);
  expect(all(red, "a", "cid")[0].attrs.href).toBe("https://pubchem.ncbi.nlm.nih.gov/compound/16129778");
  expect(texts(red, "a", "cid")[0]).toBe("CID 16129778");
});

test("the dip player rests after its fourth dip, lifted into the air, with the atoms counted", () => {
  const dip = drawn("shared/chemistry/indigo-vat-dip");
  expect(all(dip, "figure")[0].attrs).toMatchObject({ class: "vat", id: "fig1", "data-dips": "4", "data-pose": "air" });
  expect(all(dip, "li", "vs").map((phase) => [phase.attrs["data-pose"], phase.attrs["aria-current"]])).toEqual([["vat", undefined], ["lifted", undefined], ["air", "step"]]);
  expect(texts(dip, "button", "vat-dip")).toEqual(["Dip again"]);
  expect(all(dip, "span", "dsw").map((swatch) => swatch.attrs.style)).toEqual(["background:var(--dip-1)", "background:var(--dip-2)", "background:var(--dip-3)", "background:var(--dip-4)"]);
  expect(all(dip, "div", "eq")[0].attrs["aria-label"]).toBe("Two leucoindigo plus oxygen gives two indigo plus two water");
  expect(texts(dip, "span", "vh")).toEqual(["balanced", "balanced", "balanced", "balanced"]);
});

test("the stage player rests on stage 11 of 11 and hands the page script its stages", () => {
  const stages = drawn("kutch-ajrakh/process/cloth-after-each-stage");
  const cloth = all(stages, "div", "lc")[0].attrs;
  expect(cloth["data-rest"]).toBe("11");
  expect(JSON.parse(cloth["data-stages"])[0]).toEqual({ n: 1, name: "saaj", eng: "Scouring", local: true, after: "bright white and soft" });
  expect(texts(stages, "p", "lc-k")).toEqual(["Stage 11 of 11"]);
  expect(texts(stages, "p", "lc-now")).toEqual(["Cloth afterbrighter red and blue"]);
  const ribbon = all(stages, "button", "rb");
  expect(ribbon).toHaveLength(11);
  expect([ribbon[0].attrs["aria-label"], ribbon[3].attrs["aria-label"]]).toEqual(["1 saaj", "4 Drying"]);
  expect(all(stages, "li", "lc-step")[10].attrs).toMatchObject({ id: "a-st-11", "aria-current": "step" });
});

test("a 3D molecule sets its dial from its yaw, in whole degrees", () => {
  const trio = drawn("shared/chemistry/indican-indigo-leucoindigo-3d");
  expect(all(trio, "figure", "mol").map((model) => model.attrs["data-cid"])).toEqual(["441564", "5318432", "23035"]);
  const dial = all(trio, "div", "mol-dial")[0].attrs;
  expect([dial["aria-valuenow"], dial["aria-valuetext"], dial["aria-label"]]).toEqual(["24", "Turned 24 degrees", "Turn the indican model"]);
  expect(texts(trio, "a")[0]).toBe("PubChem CID 441564");
  expect(all(trio, "div", "mol-grid")[0].attrs.class).toBe("mol-grid n3");
});

test("a diagram is a drawing or a chain whose steps link into the reaction player", () => {
  const well = drawn("kutch-ajrakh/geology/ajrakhpur-borewell-depth");
  expect(all(well, "svg")[0].attrs.class).toBe("well-svg kv-well");
  expect(texts(well, "text")).toContain("450 ft");
  const chain = drawn("shared/chemistry/indigo-leaf-to-cloth-chain");
  expect(all(chain, "section", "chain")[0].attrs["aria-labelledby"]).toBe("ch-h");
  expect(all(chain, "a", "inline")[0].attrs).toMatchObject({ href: "#rp-blue", "data-rp-step": "rp-blue:1" });
  expect(texts(chain, "a", "inline")[0]).toBe("Fig. 4, step 1");
});

test("the equation card shows the source's step 2 as a hypothesis that does not balance", () => {
  const card = drawn("kutch-ajrakh/chemistry/indoxyl-to-indigo-hypothesis");
  expect(all(card, "div")[0].attrs.class).toBe("kv-hyp wrap");
  expect(texts(card, "small")).toEqual(["indoxyl", "as the source words it", "indigo"]);
  expect(texts(card, "span", "arrow")).toEqual(["→"]);
});

test("a structure diagram names each molecule and its PubChem record beside the drawing", () => {
  const figure = drawn("shared/chemistry/alizarin-aluminium-ring-structures");
  expect(all(figure, "figure")[0].attrs).toMatchObject({ id: "fig3-en", "aria-labelledby": "f3-t-en" });
  expect(texts(figure, "b")).toEqual(["Alizarin", "Purpurin"]);
  expect(texts(figure, "span").filter((text) => text.startsWith("PubChem"))).toEqual(["PubChem CID 6293", "PubChem CID 6683"]);
  expect(texts(figure, "p", "m-key")).toEqual(["Marked: the ring that closes on aluminium, and the hydroxyl purpurin adds"]);
});

test("the model explainer shows inert stills and runs the model's document sandboxed", () => {
  const explainer = drawn("shared/chemistry/indigo-in-cotton-fibre-explainer");
  expect(all(explainer, "div", "model-still").map((still) => [still.attrs.class, "inert" in still.attrs])).toEqual([["model-still wide", true], ["model-still narrow", true]]);
  const frame = all(explainer, "iframe")[0].attrs;
  expect([frame.sandbox, frame.title, frame.style]).toEqual(["allow-scripts", "Model-built explainer: inside one cotton fibre, the vat then the air", "height:760px"]);
  expect(frame["data-srcdoc"].startsWith("<!doctype html>")).toBe(true);
  expect(all(explainer, "input")[0].attrs).toMatchObject({ type: "range", max: "1000", value: "750" });
});

test("the material cards draw six materials and place the photograph nested in them", () => {
  const cards = drawn("kutch-ajrakh/materials/six-materials");
  expect(all(cards, "section")[0].attrs).toMatchObject({ id: "materials", "aria-labelledby": "mat-h" });
  expect(texts(cards, "h3")).toEqual(["Six materials"]);
  expect(all(cards, "div", "mat")).toHaveLength(6);
  expect(all(cards, "span", "msw").map((swatch) => swatch.attrs.style ?? swatch.attrs.class)).toEqual([
    "background:var(--dye-indigo)",
    "background:var(--dye-madder)",
    "msw crys",
    "background:var(--dye-kut)",
    "background:var(--dye-harda)",
    "background:var(--dye-lime)"
  ]);
  expect(all(cards, "kv-component").map((slot) => slot.attrs.label)).toEqual(["kutch-ajrakh/materials/natural-dye-materials-photo"]);
});

test("the lab opens on the blue vat and keeps its other experiments closed until chosen", () => {
  const lab = drawn("kutch-ajrakh/chemistry/what-if-lab", (label) => (byLabel.get(label)!.kind === "choice_toggle" ? view(label) : placeholder(label)));
  expect(all(lab, "button").filter((button) => "data-x" in button.attrs).map((button) => [button.attrs["data-x"], button.attrs["aria-pressed"]])).toEqual([["blue", "true"], ["red", "false"], ["water", "false"]]);
  expect(all(lab, "div", "lab-panel").map((panel) => [panel.attrs["data-exp"], "hidden" in panel.attrs])).toEqual([["blue", false], ["red", true], ["water", true]]);
});

test("a choice toggle drawn on its own is open, on its first option, with its switch off", () => {
  const red = drawn("kutch-ajrakh/chemistry/what-if-red-dye");
  expect("hidden" in all(red, "div", "lab-panel")[0].attrs).toBe(false);
  expect(all(red, "button").filter((button) => "data-v" in button.attrs).map((button) => button.attrs["aria-pressed"])).toEqual(["true", "false"]);
  expect(all(red, "div").filter((result) => "data-res" in result.attrs).map((result) => "hidden" in result.attrs)).toEqual([false, true]);
  expect(all(red, "button", "switch")[0].attrs).toMatchObject({ role: "switch", "aria-checked": "false", "aria-labelledby": "sw-pa", "data-pa-sw": "" });
  expect(texts(red, "button", "btn")).toEqual(["Another day of tapano"]);
});

test("the process replay rests finished, with the sources it read and the sections it wrote", () => {
  const replay = drawn("kutch-ajrakh/overview/how-this-answer-was-made");
  const stages = all(replay, "li", "is-done");
  expect(stages.map((stage) => [stage.attrs["data-kv-a"], stage.attrs["data-kv-b"]])[0]).toEqual(["0", "600"]);
  expect(stages).toHaveLength(5);
  expect(all(replay, "li", "kv-ms")).toHaveLength(44);
  expect(all(replay, "span", "rel")[13].attrs.class).toBe("rel C");
  expect(all(replay, "li", "kv-mw")).toHaveLength(7);
  expect(texts(replay, "button")).toEqual(["Watch it being made"]);
});

test("the client knows the same science kinds as the backend, and draws each of them", () => {
  const registry = readFileSync(join(__dirname, "..", "..", "backend", "app", "research", "component_specs_science.py"), "utf8");
  const backend = [...registry.matchAll(/^\s+"([a-z0-9_]+)": [A-Z]\w+Spec,$/gm)].map((found) => found[1]);
  expect([...SCIENCE_KINDS]).toEqual(backend);
  expect(Object.keys(VIEWS).sort()).toEqual([...SCIENCE_KINDS]);
});

test("every Ajrakh spec file of a science kind passes the client's shape for its kind", () => {
  const science = content.components.filter((component) => (SCIENCE_KINDS as readonly string[]).includes(component.kind));
  expect(science).toHaveLength(21);
  for (const component of science) {
    const spec = JSON.parse(readFileSync(join(AJRAKH_DIR, "specs", `${component.label.replaceAll("/", "__")}.json`), "utf8"));
    expect(() => parseShape(SPEC_SHAPES_SCIENCE[component.kind as ScienceKind], spec), component.label).not.toThrow();
  }
});

test("a drawing in a spec refuses handlers, script links, foreign references and untokened paint", () => {
  for (const attrs of [{ onclick: "go()" }, { href: "javascript:go()" }, { fill: "url(https://example.org/a.svg#x)" }, { fill: "#5f01d1" }, { fill: "var(--brand-purple)" }]) {
    expect(() => parseShape(svgNodeShape, { tag: "rect", attrs })).toThrow(ShapeError);
  }
  expect(parseShape(svgNodeShape, { tag: "rect", attrs: { fill: "color-mix(in srgb, var(--dye-cloth) 80%, var(--dye-mud))" } }).attrs).toBeTruthy();
});
