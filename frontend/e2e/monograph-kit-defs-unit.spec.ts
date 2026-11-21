import { expect, test } from "@playwright/test";

import { KIT_DEFS, KIT_STYLE_REFERENCES } from "@/generated/kitDefs";
import type { MonographDocument } from "@/lib/monographDocument";
import { defsByScope, drawnScopes, kitDrawnIds, pageDefs, referencedIds, usedDefs, type KitDef } from "@/lib/monographKitDefs";

const def = (scope: string | null, markup: string): KitDef => ({ scope, markup });

const DEFS: Record<string, KitDef> = {
  "ag-C": def("chem", '<radialGradient id="ag-C"><stop offset="0"/></radialGradient>'),
  "chem-weave": def("chem", '<pattern id="chem-weave"><path d="M0 3 L3 0"/></pattern>'),
  "tile-1": def("pt", '<pattern id="tile-1"><rect fill="url(#chem-weave)"/></pattern>'),
  unused: def("pt", '<pattern id="unused"><path d="M0 0"/></pattern>')
};

test("a drawing's references are found by url() and by a use element's href, never by a page anchor", () => {
  expect(referencedIds('<circle fill="url(#ag-C)"/><use href="#tile-1"/><use href=\'#ag-H\'/>')).toEqual(["ag-C", "tile-1", "ag-H"]);
  expect(referencedIds("plain text with # and url(nothing)")).toEqual([]);
  expect(referencedIds('<a href="#sources">Sources</a>')).toEqual([]);
  expect(referencedIds(JSON.stringify({ tag: "use", attrs: { href: "#hd-plait", "xlink:href": "#vlg-base" } }))).toEqual(["hd-plait", "vlg-base"]);
});

test("a page carries only the definitions its drawings use, following one definition into another", () => {
  const spec = JSON.stringify({ atoms: [{ fill: "url(#ag-C)" }, { fill: "url(#ag-C)" }], cloth: { tag: "use", attrs: { href: "#tile-1" } }, missing: "url(#not-defined)" });
  expect(usedDefs([spec], DEFS)).toEqual([DEFS["ag-C"], DEFS["tile-1"], DEFS["chem-weave"]]);
  expect(usedDefs(["no drawing here"], DEFS)).toEqual([]);
});

test("a definition the page already holds is never added twice", () => {
  const fragment = '<svg><defs><radialGradient id="ag-C"/></defs><circle fill="url(#ag-C)"/><rect fill="url(#chem-weave)"/></svg>';
  expect(usedDefs([fragment], DEFS)).toEqual([DEFS["chem-weave"]]);
  expect(usedDefs([JSON.stringify({ tag: "pattern", attrs: { id: "tile-1" } }), "url(#tile-1)"], DEFS)).toEqual([]);
});

test("definitions are grouped by the scope whose colours they read", () => {
  expect(defsByScope([DEFS["ag-C"], DEFS["tile-1"], DEFS["chem-weave"]])).toEqual([
    { scope: "chem", markup: [DEFS["ag-C"].markup, DEFS["chem-weave"].markup] },
    { scope: "pt", markup: [DEFS["tile-1"].markup] }
  ]);
});

test("the atom gradients a borrowed molecule fills its atoms with are kept in the chemistry scope, whose colours they read", () => {
  for (const id of ["ag-C", "ag-H", "ag-N", "ag-O"]) {
    expect(KIT_DEFS[id].markup, id).toContain(`id="${id}"`);
    expect(KIT_DEFS[id].scope, id).toBe("chem");
  }
});

function generated(components: { label: string; kind: string; spec: Record<string, unknown> }[]): MonographDocument {
  const listed = components.map(({ label, kind }) => ({ label, kind, chapter: "process", anchor: "#x", title: label, description: "", field: "PROCESS", fields: [], subjects: [] }));
  return { content: { components: listed }, specs: Object.fromEntries(components.map(({ label, spec }) => [label, spec])), fragments: {} } as unknown as MonographDocument;
}

test("a stage list the kit draws asks for the weave and the tile of each stage that names no swatch", () => {
  const stages = { key: "lc", stages: [{ name: "Wash", swatch: "--dye-cloth" }, { name: "Mordant", swatch: null }, { name: "Dye" }] };
  expect(kitDrawnIds("stage_player", stages)).toEqual(["tile-2", "tile-3", "pt-weave"]);
  expect(kitDrawnIds("answer_block", stages)).toEqual([]);
  expect(kitDrawnIds("related_crafts", { weave: "pt-weave", crafts: [{ tile: 4 }, { tile: 7 }] })).toEqual(["pt-weave", "tile-4", "tile-7"]);
  expect(kitDrawnIds("voice", { coda: { tile: "tile-9", weave: "pt-weave" } })).toEqual(["tile-9", "pt-weave"]);
});

test("a generated page carries the kit's weave and tiles its stage list draws and the hatches its scopes' style fills with", () => {
  const document = generated([{ label: "bagru/process/stages", kind: "stage_player", spec: { key: "lc", stages: [{ name: "Wash" }] } }]);
  expect(drawnScopes(document)).toEqual(["pt"]);
  const carried = pageDefs(document, KIT_DEFS, KIT_STYLE_REFERENCES).map((found) => found.markup);
  for (const id of ["tile-1", "pt-weave", "hatch-madder"]) expect(carried.some((markup) => markup.includes(`id="${id}"`)), id).toBe(true);
  expect(KIT_STYLE_REFERENCES).toEqual({ pt: ["hatch-madder"], sa: ["hatch-place"] });
  expect(pageDefs(generated([]), KIT_DEFS, KIT_STYLE_REFERENCES)).toEqual([]);
});
