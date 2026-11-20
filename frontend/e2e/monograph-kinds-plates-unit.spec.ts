import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { VIEWS as DATA_VIEWS } from "@/components/monograph/kinds/data";
import { HeldOrUnitText, HeldText } from "@/components/monograph/kinds/plates/HeldText";
import { VIEWS } from "@/components/monograph/kinds/plates";
import { playerClock } from "@/components/monograph/kinds/plates/mediaCopy";
import { reliabilityLabel } from "@/components/monograph/kinds/plates/PlateMasthead";
import { drawingShape, heldOrUnitShape, heldTextShape, picturePlateShape, swatchPairShape } from "@/lib/componentSpecsPlates";
import type { ComponentViews } from "@/lib/componentViewContract";
import { parseShape, ShapeError } from "@/lib/shape";

import { anchorOf, anchorsHeldWithoutView, approvedMarkup, canonical, componentsOfKinds, drawnView, specOf } from "./monographKinds";

const PLATE_KINDS = ["picture_plate", "ai_illustration", "specimen_plate", "label_card", "swatch_cards", "swatch_pair", "film", "ai_video", "comic", "audio_player", "voice", "credits"];
const LANE_VIEWS: ComponentViews = { ...VIEWS, ...DATA_VIEWS };

test("the plates group draws every one of its kinds", () => {
  expect(Object.keys(VIEWS).sort()).toEqual([...PLATE_KINDS].sort());
});

for (const component of componentsOfKinds(PLATE_KINDS)) {
  test(`${component.label} draws the approved page's markup from its spec`, () => {
    const view = VIEWS[component.kind];
    if (!view) throw new Error(`no view for ${component.kind}`);
    const approved = canonical(approvedMarkup(anchorOf(component), anchorsHeldWithoutView(component, LANE_VIEWS)));
    expect(canonical(drawnView(view, component, LANE_VIEWS))).toEqual(approved);
  });
}

test("the GI card holds the ladder it names, and draws without it when no renderer passes it in", () => {
  const card = componentsOfKinds(["label_card"])[0];
  if (!VIEWS.label_card) throw new Error("the GI card has a view");
  expect(drawnView(VIEWS.label_card, card, LANE_VIEWS)).toContain('<div class="gi-ladder"><p class="fig-no" data-fig="pt:6">');
  expect(drawnView(VIEWS.label_card, card)).not.toContain("gi-ladder");
});

test("the Rann opener draws its picture under the chapter's title, with the units in their places", () => {
  const rann = componentsOfKinds(["picture_plate"]).find((component) => component.label === "shared/geography/great-rann-of-kachchh-photo");
  if (!rann || !VIEWS.picture_plate) throw new Error("the Rann opener is on the page");
  const html = drawnView(VIEWS.picture_plate, rann);
  expect(html).toContain('<div class="opener chapter-photo"><div class="op-ph"><img src="/monographs/kutch-ajrakh/img/rann-of-kachchh-white-desert.jpg"');
  expect(html).toContain('<h2 class="t-h2" id="why-h"><kv-slot unit="u0587"></kv-slot></h2>');
  expect(html).toContain('<p class="op-credit"><kv-slot unit="u0589"></kv-slot></p>');
});

test("a held citation is drawn as the page draws it: numbers in order, named and described", () => {
  const nodes = parseShape(heldTextShape, [
    {
      m: "s",
      c: ["Khamir, ", { m: "cite", key: "pt:C035", g: ["g14", "g1"], shown: [{ number: 1, title: "GI Journal" }, { number: 14, title: "Khatris" }], c: ["Dhamadka"] }]
    }
  ]);
  expect(renderToStaticMarkup(createElement(HeldText, { nodes }))).toBe(
    '<span class="s">Khamir, <span class="nw">Dhamadka<button class="kcite" type="button" data-c="pt:C035" data-g="g14 g1" aria-haspopup="dialog" aria-expanded="false" aria-label="Sources 1 and 14" aria-description="GI Journal; Khatris">1,14</button></span></span>'
  );
});

test("held text refuses an unknown mark and a citation whose numbers are out of order", () => {
  expect(() => parseShape(heldTextShape, [{ m: "script", c: ["x"] }])).toThrow(ShapeError);
  expect(() => parseShape(heldTextShape, [{ m: "cite", key: "k", g: ["g2", "g1"], shown: [{ number: 2, title: "B" }, { number: 1, title: "A" }] }])).toThrow(ShapeError);
  expect(() => parseShape(heldTextShape, [])).toThrow(ShapeError);
});

test("a drawing refers only within its page and carries no handler", () => {
  expect(parseShape(drawingShape, { tag: "use", attrs: { href: "#ai-vat" }, children: [] }).attrs.href).toBe("#ai-vat");
  expect(() => parseShape(drawingShape, { tag: "use", attrs: { href: "https://example.org/x.svg#a" }, children: [] })).toThrow(ShapeError);
  expect(() => parseShape(drawingShape, { tag: "rect", attrs: { onclick: "go()" }, children: [] })).toThrow(ShapeError);
  expect(() => parseShape(drawingShape, { tag: "foreignObject", attrs: {}, children: [] })).toThrow(ShapeError);
});

test("a plate spec names its picture under the monograph's pictures and a swatch pair has two swatches", () => {
  const plate = specOf("kutch-ajrakh/design/indigo-ground-print-photo");
  expect(parseShape(picturePlateShape, plate).picture.width).toBe(1280);
  expect(() => parseShape(picturePlateShape, { ...plate, picture: { ...(plate.picture as object), src: "https://example.org/a.jpg" } })).toThrow(ShapeError);
  const pair = specOf("kutch-ajrakh/chemistry/iron-on-purpose-and-by-accident");
  expect(() => parseShape(swatchPairShape, { ...pair, swatches: (pair.swatches as unknown[]).slice(0, 1) })).toThrow(ShapeError);
});

test("a player's clock reads minutes and seconds, and the reliability strip names each grade's count", () => {
  expect(playerClock(56000)).toBe("0:56");
  expect(playerClock(8000)).toBe("0:08");
  expect(playerClock(125000)).toBe("2:05");
  expect(reliabilityLabel(20, [{ grade: "A", count: 9 }, { grade: "B", count: 7 }, { grade: "C", count: 4 }])).toBe("Reliability of the 20 sources: 9 graded A, 7 graded B, 4 graded C");
});

test("a cited passage in a spec is a text unit or held text, and a unit is drawn by the page's own renderer", () => {
  expect(parseShape(heldOrUnitShape, "u1104")).toBe("u1104");
  expect(parseShape(heldOrUnitShape, ["Khamir"])).toEqual(["Khamir"]);
  expect(() => parseShape(heldOrUnitShape, "Panel one")).toThrow(ShapeError);
  expect(() => parseShape(heldOrUnitShape, [])).toThrow(ShapeError);
  const unit = (ref: string) => createElement("kv-slot", { unit: ref });
  expect(renderToStaticMarkup(createElement(HeldOrUnitText, { value: "u1104", renderUnit: unit }))).toBe('<kv-slot unit="u1104"></kv-slot>');
  expect(renderToStaticMarkup(createElement(HeldOrUnitText, { value: ["Khamir, ", { m: "i", c: ["Khatris"] }], renderUnit: unit }))).toBe("Khamir, <i>Khatris</i>");
});
