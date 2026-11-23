import { expect, test } from "@playwright/test";

import { referencedClaimIds } from "@/lib/craftPageChecks";
import { ShapeError } from "@/lib/shape";

import { curatedPage, registerPage } from "./craftPageFixture";

test("a craft with no dossier still has a complete page: family, GI status, kin and three questions", () => {
  const page = registerPage();
  expect([page.curated, page.depth.basis, page.claims.length]).toEqual([false, "REGISTER", 0]);
  const kin = [...new Set(page.sameFamily.flatMap((relative) => relative.lede?.sources.map((source) => source.id) ?? []))];
  expect(page.sources.map((source) => [source.id, source.group])).toEqual(kin.map((id) => [id, "KIN"]));
  expect([page.craft.familyLabel, page.craft.kindLabel, page.giCard.status]).toEqual(["Textiles", "Hand block printing", "GI"]);
  expect(page.suggestedQuestions).toHaveLength(3);
  expect(page.suggestedQuestions.every((question) => question.includes(page.craft.displayName))).toBe(true);
  expect([page.tabs.process, page.tabs.region, page.tabs.sources, page.tabs.evidence]).toEqual([false, true, false, false]);
  const [first] = page.sameFamily;
  expect([first.craft.slug, first.basis, first.coverage]).toEqual(["Kutch-Ajrakh", "CURATED", "FULL"]);
  expect(first.hero?.media.display).toBe("INLINE");
  expect(first.lede?.sources.map((source) => source.id)).toEqual([...new Set(first.lede?.citations.map((citation) => citation.sourceId))]);
  for (const list of [page.events, page.environment, page.sourcesDiffer, page.places, page.pictures, page.craft.localNames]) expect(Array.isArray(list)).toBe(true);
});

test("the curated page carries its GI card, dated events, environment steps and stage disagreements", () => {
  const page = curatedPage();
  expect([page.giCard.applicationNumber, page.giCard.filedOn, page.giCard.registeredOn]).toEqual(["1050", "2023-01-31", "2024-04-22"]);
  const kinds = new Set(page.events.map((event) => event.kind));
  expect([...kinds].sort()).toEqual(["GI_FILED", "GI_REGISTERED", "PRICE", "STATED", "WORKFORCE"]);
  expect(page.events.map((event) => event.start)).toEqual([...page.events.map((event) => event.start)].sort((a, b) => a - b));
  expect(page.environment[0].place?.name).toBe("Dhamadka River (Suran)");
  const keys = new Set(page.sourcesDiffer.map((row) => row.key));
  expect(page.process.stages.flatMap((stage) => stage.differ).every((key) => keys.has(key))).toBe(true);
  expect(page.pictures.filter((picture) => picture.role === "HERO")).toHaveLength(1);
  expect(page.sameFamily.every((relative) => relative.craft.slug !== page.craft.slug)).toBe(true);
});

test("every reader's page lists every claim the GI card, events and environment cite", () => {
  const page = curatedPage();
  const listed = new Set(page.claims.map((claim) => claim.id));
  const context = [...page.giCard.claimIds, ...page.events.flatMap((event) => event.claimIds), ...page.environment.flatMap((step) => step.claimIds)];
  expect(context.length).toBeGreaterThan(0);
  expect(context.every((id) => listed.has(id))).toBe(true);
  expect(referencedClaimIds(page).every((id) => listed.has(id))).toBe(true);
  expect(page.tabs.evidence).toBe(true);
});

test("the client refuses a page whose new parts do not agree", () => {
  expect(() => curatedPage((body) => body.pictures.forEach((picture) => (picture.role = "HERO")))).toThrow(/one hero/);
  expect(() => curatedPage((body) => (body.process.stages[0].differ = ["differ-99"]))).toThrow(ShapeError);
  expect(() => curatedPage((body) => (body.depth = { ...body.depth, coverage: null }))).toThrow(/coverage class/);
  expect(() => curatedPage((body) => (body.events[0] = { ...body.events[0], date: String(body.events[0].end + 1) }))).toThrow(/inside the event/);
  expect(() => curatedPage((body) => (body.sameFamily[0] = { ...body.sameFamily[0], craft: { ...body.craft } }))).toThrow(ShapeError);
  expect(() => curatedPage((body) => (body.sourcesDiffer[1] = { ...body.sourcesDiffer[1], key: body.sourcesDiffer[0].key }))).toThrow(/own key/);
  expect(() => curatedPage((body) => (body.sourcesDiffer[0] = { ...body.sourcesDiffer[0], weight: 4 }))).toThrow(ShapeError);
  expect(() => curatedPage((body) => (body.communities[0] = { ...body.communities[0], placeKey: "nowhere" }))).toThrow(/not nowhere/);
  expect(() => curatedPage((body) => (body.environment[0] = { ...body.environment[0], place: { key: "nowhere", name: "Nowhere" } }))).toThrow(/not nowhere/);
  expect(() => curatedPage((body) => (body.environment[0] = { ...body.environment[0], factor: "WIND" as never }))).toThrow(ShapeError);
});

test("a craft page lists the local names its dossier states, each on a claim it lists, and none without a dossier", () => {
  const page = curatedPage();
  expect(page.craft.localNames.map((name) => [name.name, name.language, name.script])).toEqual([
    ["اجرڪ", "sd", "Arab"],
    ["ajrak", "sd", "Latn"]
  ]);
  const listed = new Set(page.claims.map((claim) => claim.id));
  expect(page.craft.localNames.flatMap((name) => name.claimIds).every((id) => listed.has(id))).toBe(true);
  const unlisted = "00000000-0000-4000-8000-000000000000";
  expect(() => curatedPage((body) => (body.craft = { ...body.craft, localNames: [{ ...body.craft.localNames[0], claimIds: [unlisted] }] }))).toThrow(/a claim the page lists/);
  expect(registerPage().craft.localNames).toEqual([]);
});
