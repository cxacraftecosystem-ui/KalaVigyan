import { expect, test } from "@playwright/test";

import { documentLanguagePath, isDocumentLanguage, languageAlternates, parsePageLanguages, readLanguages, unitLanguage, type PageLanguage } from "../lib/documentLanguages";
import { draftVariant, isTranslatable, passageLeaves } from "../lib/documentVariant";
import type { MonographDocument, MonographNode } from "../lib/monographDocument";
import { parseMonographDocument } from "../lib/monographDocumentShape";
import { filledPassages, taskPage, translatedTexts, type PassageView } from "../lib/translationContract";

const CITE = { m: "cite", key: "c2", g: ["g1", "g4"], c: ["shrub."] };
const PLANT: MonographNode[] = [{ m: "s", sid: "s1", c: ["The dye comes from ", { m: "i", role: "bot", c: ["Indigofera tinctoria"] }, ", a ", CITE] }];
const HINDI = ["रंग ", "Indigofera tinctoria", " से आता है, जो एक ", "झाड़ी है।"];

function language(code: "hi" | "gu", translated: number): PageLanguage {
  const names = { hi: ["Hindi", "हिन्दी", "Deva"], gu: ["Gujarati", "ગુજરાતી", "Gujr"] }[code];
  return { code, label: names[0], autonym: names[1], script: names[2], direction: "ltr", passages: 12, translated, offered: true };
}

function document(): MonographDocument {
  return parseMonographDocument({
    schemaVersion: 1,
    subjectKind: "craft",
    subjectSlug: "Kutch-Bandhani",
    language: "en",
    title: "Kutch Bandhani",
    version: 11,
    content: {
      schemaVersion: 1,
      craftSlug: "Kutch-Bandhani",
      sources: {},
      citations: {},
      citationClaims: {},
      data: {},
      units: {
        "masthead-title": { chapter: "opening", tag: "h1", field: null, nodes: ["Kutch Bandhani"], claimIds: [] },
        plant: { chapter: "made", tag: "p", field: "MATERIALS", nodes: PLANT, claimIds: ["c-2"] },
        lede: { chapter: "opening", tag: "p", field: "OVERVIEW", nodes: ["Bandhani is a tie-dye craft."], claimIds: ["c-1"] },
        year: { chapter: "history", tag: "dd", field: null, nodes: ["1998"], claimIds: [] }
      },
      components: [],
      layout: []
    },
    specs: {},
    fragments: {},
    shell: null,
    pageUrl: "https://kalavigyan.example/crafts/Kutch-Bandhani"
  });
}

test("a passage's texts are its leaves in order, names fixed and the citation marked, as the server reads them", () => {
  expect(passageLeaves(PLANT)).toEqual([
    { text: "The dye comes from ", fixed: false, cited: false },
    { text: "Indigofera tinctoria", fixed: true, cited: false },
    { text: ", a ", fixed: false, cited: false },
    { text: "shrub.", fixed: false, cited: true }
  ]);
  expect([isTranslatable("masthead-title", ["Kutch Ajrakh"]), isTranslatable("u2", ["1998"]), isTranslatable("u4", ["12th century"])]).toEqual([false, false, true]);
});

test("a draft translation draws its passage in its language, keeps the citation and marks every other passage English", () => {
  const variant = draftVariant(document(), "hi", "Deva", [{ key: "plant", english: ["The dye comes from ", "Indigofera tinctoria", ", a ", "shrub."], texts: HINDI }]);
  const units = variant.content.units;
  expect([units.plant.lang, units.lede.lang, units["masthead-title"].lang, units.year.lang]).toEqual(["hi", "en", undefined, undefined]);
  expect(units.plant.nodes).toEqual([{ m: "s", sid: "s1", c: ["रंग ", { m: "i", role: "bot", c: ["Indigofera tinctoria"] }, " से आता है, जो एक ", { ...CITE, c: ["झाड़ी है।"] }] }]);
  expect(variant.translation).toEqual({ sourceLanguage: "en", sourceVersion: 11, script: "Deva", direction: "ltr", passages: 2, translated: 1, held: 0 });
  const stale = draftVariant(document(), "hi", "Deva", [{ key: "plant", english: ["The dye is made from ", "Indigofera tinctoria", ", a ", "shrub."], texts: HINDI }]);
  expect(stale.content.units.plant.lang).toBe("en");
  expect(parseMonographDocument(JSON.parse(JSON.stringify(variant))).translation?.translated).toBe(1);
});

test("a unit says its language: a translated one its script and direction, a fallback that it is English", () => {
  const variant = draftVariant(document(), "hi", "Deva", [{ key: "plant", english: ["The dye comes from ", "Indigofera tinctoria", ", a ", "shrub."], texts: HINDI }]);
  expect(unitLanguage(variant.content.units.plant)).toEqual({ lang: "hi", dir: "ltr", "data-script": "Deva" });
  expect(unitLanguage(variant.content.units.lede)).toEqual({ lang: "en", dir: "ltr", "data-fallback": "en" });
  expect(unitLanguage(document().content.units.lede)).toEqual({});
  expect(unitLanguage({ ...document().content.units.lede, lang: "ur" })).toEqual({ lang: "ur", dir: "rtl", "data-script": "Aran" });
});

test("a page's languages follow the answer languages' codes, and search engines are told only of the translated ones", () => {
  expect([isDocumentLanguage("hi"), isDocumentLanguage("ur"), isDocumentLanguage("en"), isDocumentLanguage("v3")]).toEqual([true, true, false, false]);
  expect([documentLanguagePath("craft", "Kutch-Bandhani", "hi"), documentLanguagePath("category", "Textiles", "en"), documentLanguagePath("family", "Other-Textiles", "gu")]).toEqual([
    "/crafts/Kutch-Bandhani/hi",
    "/categories/Textiles",
    "/crafts/Other-Textiles/gu"
  ]);
  const languages = [language("gu", 0), language("hi", 3)];
  expect(readLanguages(languages).map((each) => each.code)).toEqual(["hi"]);
  expect(languageAlternates("craft", "Kutch-Bandhani", languages)).toEqual({ en: "/crafts/Kutch-Bandhani", hi: "/crafts/Kutch-Bandhani/hi", "x-default": "/crafts/Kutch-Bandhani" });
  expect(languageAlternates("craft", "Kutch-Bandhani", [language("gu", 0)])).toEqual({});
  const parsed = parsePageLanguages({ schemaVersion: 1, subject: { kind: "craft", slug: "Kutch-Bandhani" }, languages });
  expect(parsed.languages[1].autonym).toBe("हिन्दी");
});

test("a TRANSLATE task names its page and language, and only written passages are sent, fixed texts as they stand", () => {
  expect(taskPage("TRANSLATE:craft:Kutch-Bandhani:gu")).toEqual({ kind: "craft", slug: "Kutch-Bandhani", language: "gu" });
  expect([taskPage("MISSING_FIELD:craft:Kutch-Bandhani:HISTORY"), taskPage("TRANSLATE:craft:Kutch-Bandhani:en")]).toEqual([null, null]);
  const passage: PassageView = {
    key: "plant",
    sourceHash: "a".repeat(64),
    english: "The dye comes from Indigofera tinctoria, a shrub.",
    texts: ["The dye comes from ", "Indigofera tinctoria", ", a ", "shrub."],
    fixed: [1],
    cited: [3],
    chapter: "made",
    tag: "p",
    state: "TO_TRANSLATE"
  };
  expect(translatedTexts(passage, { 0: "रंग ", 1: "changed", 2: " से आता है, जो एक ", 3: "झाड़ी है।" })).toEqual(HINDI);
  const other = { ...passage, key: "lede" };
  expect(filledPassages([passage, other], { plant: { 0: "रंग " }, lede: { 0: "  " } })).toEqual([{ key: "plant", sourceHash: "a".repeat(64), texts: ["रंग ", "Indigofera tinctoria", "", ""] }]);
});
