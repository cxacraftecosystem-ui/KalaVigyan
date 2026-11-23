import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { PageBlock } from "@/components/monograph/kinds/blocks/answerBlockSpec";
import { checkedCraftPage } from "@/lib/craftPageChecks";
import { craftPageShape, type CraftPage, type OverviewSection, type PageClaim, type PageEvidence } from "@/lib/craftPageContract";
import type { PageGi } from "@/lib/craftPageContext";
import { parseShape } from "@/lib/shape";

export const CRAFT_PAGE_GOLDEN = join(__dirname, "..", "..", "shared", "craft.page.golden.json");
export const REGISTER_PAGE_GOLDEN = join(__dirname, "..", "..", "shared", "craft.page.register.golden.json");
export const STORED_SECTION_LIMIT = 8;

type GoldenStructure = { chapters: { items: { block: PageBlock | null }[] }[] };

export function rawPage(): CraftPage {
  return JSON.parse(readFileSync(CRAFT_PAGE_GOLDEN, "utf8")) as CraftPage;
}

export function goldenBlock(kind: string): PageBlock {
  const golden = JSON.parse(readFileSync(CRAFT_PAGE_GOLDEN, "utf8")) as GoldenStructure;
  for (const chapter of golden.chapters) for (const item of chapter.items) if (item.block && item.block.kind === kind) return item.block;
  throw new Error(`the golden page's structure draws no ${kind}`);
}

export function registerPage(edit: (body: CraftPage) => void = () => undefined): CraftPage {
  const body = JSON.parse(readFileSync(REGISTER_PAGE_GOLDEN, "utf8")) as CraftPage;
  edit(body);
  return checkedCraftPage(parseShape(craftPageShape, body));
}

function withoutRecord(gi: PageGi): PageGi {
  return { status: gi.status, applicationNumber: null, certificateNumber: null, filedOn: null, registeredOn: null, journalIssue: null, proprietors: [], authorisedUserCount: null, claimIds: [] };
}

export function curatedPage(edit: (body: CraftPage) => void = () => undefined): CraftPage {
  const body = rawPage();
  edit(body);
  return checkedCraftPage(parseShape(craftPageShape, body));
}

export function pageEvidence(page: CraftPage): PageEvidence {
  return page.evidence;
}

function storedSections(claims: readonly PageClaim[], titles: Map<string, string>): OverviewSection[] {
  const sections = new Map<string, OverviewSection>();
  for (const claim of claims) {
    if (claim.level === "HYPOTHESIS") continue;
    const section = sections.get(claim.discipline) ?? { discipline: claim.discipline, title: titles.get(claim.discipline) ?? claim.discipline, basis: "STORED_CLAIMS", sentences: [] };
    if (section.sentences.length < STORED_SECTION_LIMIT) section.sentences.push({ id: claim.id, text: claim.text, level: claim.level, claimIds: [claim.id], terms: [] });
    sections.set(claim.discipline, section);
  }
  return [...sections.values()];
}

export function uncuratedPage(): CraftPage {
  return curatedPage((body) => {
    const titles = new Map(body.evidence.groups.map((group) => [group.discipline, group.title]));
    body.claims = body.claims.map((claim) => ({ ...claim, provenance: "SEED", sourcesDiffer: false }));
    body.curated = false;
    body.curation = null;
    body.depth = { ...body.depth, basis: "STORED_CLAIMS", coverage: null };
    body.craft = { ...body.craft, localNames: [] };
    body.giCard = withoutRecord(body.giCard);
    body.environment = [];
    body.process = { ...body.process, stages: body.process.stages.map((stage) => ({ ...stage, differ: [] })) };
    body.overview = { lede: [], keyFacts: [], sections: storedSections(body.claims, titles) };
    body.glossary = body.glossary.map((term) => ({ ...term, meaning: null, language: null, script: null, claimIds: [] }));
    body.sourcesDiffer = [];
    body.places = [];
    body.communities = [];
    body.openQuestions = [];
    body.pictures = [];
  });
}

export function emptyPage(): CraftPage {
  return curatedPage((body) => {
    body.curated = false;
    body.curation = null;
    body.tabs = { ...body.tabs, process: false, sources: false, evidence: false };
    body.depth = { basis: "REGISTER", coverage: null, claims: 0, sources: 0, stages: 0, pictures: 0 };
    body.craft = { ...body.craft, localNames: [] };
    body.giCard = withoutRecord(body.giCard);
    body.events = [];
    body.environment = [];
    body.overview = { lede: [], keyFacts: [], sections: [] };
    body.sourcesDiffer = [];
    body.places = [];
    body.communities = [];
    body.process = { processId: null, stages: [], reactions: [] };
    body.glossary = [];
    body.pictures = [];
    body.openQuestions = [];
    body.evidence = { groups: [], hypotheses: [] };
    body.claims = [];
    body.sources = [];
    body.lede = [];
    body.cite = null;
    body.masthead = { ...body.masthead, nativeName: null, gi: null, picture: null, provenance: { basis: "REGISTER", sources: 0, reliability: { a: 0, b: 0, c: 0, d: 0 }, curatedOn: null, updatedOn: null } };
  });
}
