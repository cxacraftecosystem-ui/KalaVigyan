import { apiFetch } from "@/lib/api";
import { CRAFT_PAGE_PATH, craftPageShape, type CraftPage, type EvidenceEntry, type PageEvidence } from "@/lib/craftPageContract";
import { checkDepth, checkEvents, checkRelatives } from "@/lib/craftPageContext";
import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import type { StoredLevel } from "@/lib/answerShapes";
import { parseShape, ShapeError } from "@/lib/shape";
import type { Citation } from "@/lib/types";

export async function fetchCraftPage(slug: string): Promise<CraftPage> {
  return checkedCraftPage(parseShape(craftPageShape, await apiFetch<unknown>(CRAFT_PAGE_PATH(slug))));
}

function headCitations(page: CraftPage): Citation[] {
  const { masthead } = page;
  return [...(masthead.gi?.citations ?? []), ...shownSentences(page).flatMap((sentence) => sentence.citations)];
}

export function readingSourceIds(page: CraftPage): string[] {
  return [...new Set(headCitations(page).map((citation) => citation.sourceId))];
}

export function shownSentences(page: CraftPage): ExplainerSentence[] {
  return [...(page.masthead.picture?.sentences ?? []), ...page.lede];
}

export function referencedClaimIds(page: CraftPage): string[] {
  const { overview, process } = page;
  const sentences = [...overview.lede, ...overview.sections.flatMap((section) => section.sentences)];
  const context = [...page.craft.localNames, page.giCard, ...page.events, ...page.environment];
  const rows = [...context, ...overview.keyFacts, ...page.sourcesDiffer, ...page.places, ...page.communities, ...page.glossary, ...page.pictures, ...page.openQuestions];
  const reactions = [...process.reactions, ...process.stages.flatMap((stage) => stage.reactions)];
  const items = process.stages.flatMap((stage) => [...stage.materials, ...stage.tools]);
  return [
    ...[...sentences, ...rows, ...reactions, ...items, ...process.stages].flatMap((row) => row.claimIds),
    ...process.stages.flatMap((stage) => stage.timing.map((timing) => timing.claimId))
  ];
}

function checkEvidence(evidence: PageEvidence, levels: Map<string, StoredLevel>): void {
  const filed: [EvidenceEntry, boolean][] = [
    ...evidence.groups.flatMap((group) => group.subjects.flatMap((subject) => subject.entries.map((entry) => [entry, false] as [EvidenceEntry, boolean]))),
    ...evidence.hypotheses.map((entry) => [entry, true] as [EvidenceEntry, boolean])
  ];
  const seen = new Set<string>();
  for (const [entry, hypotheses] of filed) {
    for (const id of [entry.claimId, ...entry.foldedIds]) {
      const level = levels.get(id);
      if (!level) throw new ShapeError(`evidence ${id}`, "a claim the page lists");
      if ((level === "HYPOTHESIS") !== hypotheses) throw new ShapeError(`evidence ${id}`, "hypotheses filed apart from facts");
      if (seen.has(id)) throw new ShapeError(`evidence ${id}`, "each claim filed once");
      seen.add(id);
    }
  }
  if (seen.size !== levels.size) throw new ShapeError("evidence", "every listed claim filed");
}

export function checkedCraftPage(page: CraftPage): CraftPage {
  if (page.curated !== (page.curation !== null)) throw new ShapeError("curation", "a header exactly when the page is curated");
  const levels = new Map(page.claims.map((claim) => [claim.id, claim.level]));
  if (levels.size !== page.claims.length) throw new ShapeError("claims", "each claim listed once");
  const shownClaims = headCitations(page).map((citation) => citation.claimId);
  for (const id of [...referencedClaimIds(page), ...shownClaims]) if (!levels.has(id)) throw new ShapeError(`claim ${id}`, "a claim the page lists");
  const sources = new Set(page.sources.map((source) => source.id));
  if (sources.size !== page.sources.length) throw new ShapeError("sources", "each source listed once");
  for (const claim of page.claims) {
    for (const citation of claim.citations) if (!sources.has(citation.sourceId)) throw new ShapeError(`claim ${claim.id}`, `source ${citation.sourceId} listed`);
  }
  for (const voice of page.voices) if (!sources.has(voice.sourceId)) throw new ShapeError(`voice ${voice.itemId}`, `source ${voice.sourceId} listed`);
  for (const id of readingSourceIds(page)) if (!sources.has(id)) throw new ShapeError(`source ${id}`, "a source the page lists");
  if (page.voices.length > page.fieldVoicesTotal.quotes || page.fieldPhotos.length > page.fieldVoicesTotal.images) {
    throw new ShapeError("fieldVoicesTotal", "no more field voices shown than counted");
  }
  for (const sentence of [...page.overview.lede, ...page.overview.sections.flatMap((section) => section.sentences)]) {
    if (sentence.level === "HYPOTHESIS") throw new ShapeError(`sentence ${sentence.id}`, "a sentence resting on facts, never a hypothesis");
  }
  for (const reaction of [...page.process.reactions, ...page.process.stages.flatMap((stage) => stage.reactions)]) {
    if ((reaction.equation !== null) !== reaction.balanced) throw new ShapeError(`reaction ${reaction.label}`, "an equation only when balanced");
  }
  checkEvidence(page.evidence, levels);
  checkParts(page);
  return page;
}

function checkParts(page: CraftPage): void {
  if (page.pictures.filter((picture) => picture.role === "HERO").length > 1) throw new ShapeError("pictures", "one hero picture at most");
  const keys = page.sourcesDiffer.map((row) => row.key);
  if (new Set(keys).size !== keys.length) throw new ShapeError("sourcesDiffer", "each row with its own key");
  for (const stage of page.process.stages) {
    for (const key of stage.differ) if (!keys.includes(key)) throw new ShapeError(`stage ${stage.id}`, `a sources-differ row the page lists, not ${key}`);
  }
  const placed = new Set(page.places.map((place) => place.key));
  const pointed = [...page.communities.map((group) => group.placeKey), ...page.environment.map((step) => step.place?.key ?? null)];
  for (const key of pointed) if (key !== null && !placed.has(key)) throw new ShapeError("places", `a place the page lists, not ${key}`);
  checkDepth(page.depth, "depth");
  checkEvents(page.events);
  checkRelatives(page.craft.slug, page.sameFamily);
}
