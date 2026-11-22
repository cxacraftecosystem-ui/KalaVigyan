import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CraftWithoutMonograph } from "../components/craft/CraftWithoutMonograph";
import { checkedCraftPage } from "../lib/craftPageChecks";
import { craftPageShape, type CraftPage, type NativeName } from "../lib/craftPageContract";
import { plateMaterial } from "../lib/craftPlate";
import { craftRecordView, provenanceParts, recordNativeName, recordProvenance } from "../lib/craftRecord";
import { parseShape } from "../lib/shape";

const REGISTER_PAGE = join(__dirname, "..", "..", "shared", "craft.page.register.golden.json");
const KASUTI: NativeName = { text: "ಕಸೂತಿ", lang: "kn", script: "Knda", sourceId: "wikidata-label", sourceKind: "WIKIDATA", reviewed: true };
const GAP_WORDS = /not built yet|coming soon|no data|not enough cited evidence|0 results|not curated|nothing here yet/i;

function registerPage(edit: (page: CraftPage) => void = () => undefined): CraftPage {
  const body = JSON.parse(readFileSync(REGISTER_PAGE, "utf8")) as CraftPage;
  edit(body);
  return checkedCraftPage(parseShape(craftPageShape, body));
}

test("a craft without a monograph reads its label, its record and three questions from the craft list", () => {
  const record = craftRecordView(registerPage());
  expect(record).toMatchObject({
    slug: "Farrukhabad-Prints",
    name: "Farrukhabad Prints",
    nativeName: null,
    family: "Textiles · Hand block printing",
    plateKicker: "Hand block printing",
    material: "textile",
    gi: "Registered geographical indication",
    place: "Uttar Pradesh",
    provenance: ["From the KalaVigyan craft list"],
    start: "Start the research on Farrukhabad Prints"
  });
  expect(record.facts).toEqual([
    { label: "Family", value: "Textiles" },
    { label: "Sub-family", value: "Hand block printing" },
    { label: "Home state", value: "Uttar Pradesh" },
    { label: "Practised in", value: "Uttar Pradesh" }
  ]);
  expect(record.questions.map((question) => question.href)).toEqual([
    "/ask?q=How+do+mordants+and+dyes+fix+the+colours+of+Farrukhabad+Prints+in+the+cloth%3F&craft=Farrukhabad-Prints",
    "/ask?q=What+are+the+stages+of+Farrukhabad+Prints%2C+from+plain+cloth+to+finished+print%3F&craft=Farrukhabad-Prints",
    "/ask?q=What+do+local+water+and+climate+give+to+the+colours+of+Farrukhabad+Prints%3F&craft=Farrukhabad-Prints"
  ]);
});

test("a sourced, reviewed own-script name stands with the English name and names its source; any other is held back", () => {
  expect(recordNativeName(KASUTI)).toEqual({ text: "ಕಸೂತಿ", lang: "kn", script: "Knda", sourceId: "wikidata-label", sourceKind: "wikidata", reviewed: true });
  expect(recordProvenance(KASUTI)).toBe("From the KalaVigyan craft list · Kannada name: Wikidata, CC0");
  expect(provenanceParts(KASUTI)).toEqual(["From the KalaVigyan craft list", "Kannada name: Wikidata, CC0"]);
  expect(recordProvenance({ ...KASUTI, reviewed: false })).toBe("From the KalaVigyan craft list");
  expect(recordNativeName({ ...KASUTI, script: null })).toBeNull();
  const named = craftRecordView(registerPage((page) => (page.masthead.nativeName = KASUTI)));
  const html = renderToStaticMarkup(createElement(CraftWithoutMonograph, { record: named }));
  expect(html).toContain('<span lang="kn" data-script="Knda" dir="ltr">ಕಸೂತಿ</span>');
  expect(html).toContain('<div class="kv-label-prov"><span>From the KalaVigyan craft list</span><span>Kannada name: Wikidata, CC0</span></div>');
});

test("the masthead plate sets the name at the top end and the kicker at the bottom, and the page sits in the shell's one column", () => {
  const html = renderToStaticMarkup(createElement(CraftWithoutMonograph, { record: craftRecordView(registerPage()) }));
  const plate = html.slice(html.indexOf('data-size="masthead"'));
  expect(plate).toContain('<div class="flex flex-1 flex-col items-end px-6');
  expect(plate).toContain('<span class="kv-knock kicker m-0.5 text-inherit mt-auto">Hand block printing</span>');
  expect(plate).toContain('<span class="max-w-full min-w-0 order-first lg:max-w-[52%]"><span class="kv-plate-name kv-knock" data-latin="">Farrukhabad Prints</span>');
  expect(html).not.toContain("kv-page");
  const label = html.slice(html.indexOf('data-testid="specimen-label"'));
  expect(label.indexOf("kv-label-meta")).toBeGreaterThan(0);
  expect(label.indexOf("kv-label-meta")).toBeLessThan(label.indexOf("kv-label-prov"));
});

test("the page is the plate at the masthead, the label as h1, what the list records and research to start, with no rail or citation", () => {
  const html = renderToStaticMarkup(createElement(CraftWithoutMonograph, { record: craftRecordView(registerPage()) }));
  expect(html.match(/<h1/g)).toHaveLength(1);
  expect(html).toContain('lang="en"');
  expect(html.match(/data-testid="typographic-plate"/g)).toHaveLength(2);
  expect(html).toContain('data-size="masthead"');
  expect(html).toContain('<h2 id="craft-record-h" class="kicker">What the craft list records</h2>');
  expect(html.match(/<dt/g)).toHaveLength(4);
  expect(html).toMatch(/<h2[^>]*>Start the research on Farrukhabad Prints<\/h2>/);
  expect(html.match(/href="\/ask\?q=/g)).toHaveLength(3);
  expect(html).toContain("From the KalaVigyan craft list");
  for (const absent of ['data-testid="chapter-rail"', 'data-testid="cite-this"', "<figure"]) expect(html).not.toContain(absent);
  expect(html.replace(/<[^>]+>/g, " ")).not.toMatch(GAP_WORDS);
});

test("each craft family takes its material ground, and painting, instruments and toys their own inside More crafts", () => {
  expect(plateMaterial("Textiles", "Embroidery")).toBe("textile");
  expect(plateMaterial("Natural fibre and grass", "Cane and bamboo")).toBe("fibre");
  expect(plateMaterial("Clay", null)).toBe("clay");
  expect(plateMaterial("More crafts", "Folk painting")).toBe("paint");
  expect(plateMaterial("More crafts", "Musical instruments")).toBe("instr");
  expect(plateMaterial("More crafts", "Figurines and toys")).toBe("toys");
  expect(plateMaterial("More crafts", "Jewellery")).toBe("misc");
  expect(plateMaterial(null, null)).toBe("misc");
});
