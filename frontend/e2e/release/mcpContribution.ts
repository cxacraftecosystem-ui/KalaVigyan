type Json = Record<string, unknown>;

export const CONTRIBUTION_CRAFT = "Sanganeri-Hand-Block-Printing";
export const CONTRIBUTION_FIELD = "POLICY";
export const CONTRIBUTION_SCOPE = "read contribute";
export const CONTRIBUTION_STATEMENT = "KalaVigyan release check, withdrawn within minutes: the cited page states the words quoted from it.";
export const RETRACTION_REASON = "A release check's test fact, withdrawn once a signed-out reader was seen to read it.";
export const QUOTE_MIN_CHARS = 40;
export const QUOTE_MAX_CHARS = 240;
export const TITLE_WORDS_MIN = 3;
export const KEY_PREFIX = "release-check:";
export const SOURCES_TRIED_MAX = 6;

export type SourceChoice = { url: string; title: string; licence: string | null };
export type ProposalState = { state: string; reply: Json | null };

function record(value: unknown): Json | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Json) : null;
}

function records(value: unknown): Json[] {
  return Array.isArray(value) ? value.map(record).filter((item): item is Json => item !== null) : [];
}

function titled(title: unknown): title is string {
  return typeof title === "string" && (title.match(/[^\W\d_]{2,}/gu) ?? []).length >= TITLE_WORDS_MIN;
}

export function sourceChoices(facts: Json): SourceChoice[] {
  return records(facts.sources)
    .filter((source) => typeof source.url === "string" && source.url.startsWith("https://") && titled(source.title))
    .map((source) => ({ url: String(source.url), title: String(source.title), licence: typeof source.licence === "string" ? source.licence : null }))
    .slice(0, SOURCES_TRIED_MAX);
}

export function readText(reading: Json): Json | null {
  return record(reading.text);
}

export function closedReading(reading: Json): boolean {
  return reading.readable === true && reading.openLicence === false && reading.restricted !== true;
}

export function quoteFrom(reading: Json): string | null {
  const sentences = records(reading.passages).flatMap((passage) => String(passage.text ?? "").split(/(?<=[.;:])\s+/u));
  const fit = sentences.map((sentence) => sentence.trim()).find((sentence) => sentence.length >= QUOTE_MIN_CHARS && sentence.length <= QUOTE_MAX_CHARS && !/\d/u.test(sentence));
  return fit ?? null;
}

export function proposalArguments(source: SourceChoice, quote: string, key: string): Json {
  return {
    facts: [
      {
        craft_slug: CONTRIBUTION_CRAFT,
        field: CONTRIBUTION_FIELD,
        statement: CONTRIBUTION_STATEMENT,
        sources: [{ url: source.url, title: source.title, licence: source.licence, quotes: [{ text: quote }] }],
        idempotency_key: `${KEY_PREFIX}${key}`
      }
    ]
  };
}

export function queuedProposal(batch: Json): { id: string | null; problems: string[] } {
  const [item] = records(batch.items);
  const ticket = record(item?.ticket);
  if (!item || item.accepted !== true || !ticket) return { id: null, problems: [`propose_facts did not queue the fact: ${String(item?.problem ?? batch.message ?? "no item")}`] };
  return typeof ticket.proposalId === "string" ? { id: ticket.proposalId, problems: [] } : { id: null, problems: ["the queued ticket names no proposal id"] };
}

export function proposalState(ticket: Json): ProposalState {
  return { state: String(ticket.state ?? "UNKNOWN"), reply: record(ticket.reply) };
}

export function readerProblems(reply: Json | null): string[] {
  if (!reply) return ["the finished proposal carries no reply"];
  if (reply.outcome !== "PUBLISHED") return [`the fact was not published: ${String(reply.message ?? reply.outcome)}`];
  const readers = record(reply.readers);
  if (!readers) return ["the reply does not say where readers see the fact"];
  if (readers.shown !== true) return [`the reply says readers cannot see the fact (${String(readers.reason)}): ${String(reply.message)}`];
  return typeof reply.message === "string" && reply.message.includes("Readers see it now") ? [] : ["the reply's message does not tell where readers see the fact"];
}

export function listedCitations(facts: Json, claimId: string): Json[] | null {
  const found = records(facts.facts).find((fact) => fact.id === claimId);
  return found ? records(found.citations) : null;
}

export function readerFactProblems(facts: Json, claimId: string, source: SourceChoice): string[] {
  const citations = listedCitations(facts, claimId);
  if (!citations) return [`get_facts does not show fact ${claimId} to a signed-out reader`];
  const listed = new Map(records(facts.sources).map((found) => [String(found.id), String(found.url)]));
  const cited = citations.find((citation) => listed.get(String(citation.sourceId)) === source.url);
  if (!cited) return [`the fact shows no citation of ${source.url}`];
  return cited.quote === null || cited.quote === undefined ? [] : ["a signed-out reader is shown the closed page's words"];
}

export function documentHolds(document: Json, claimId: string): boolean {
  const content = record(document.content);
  return Object.values(record(content?.units) ?? {}).some((unit) => (record(unit)?.claimIds as unknown[] | undefined)?.includes(claimId) ?? false);
}

export function fieldClaims(coverage: Json, field: string): number | null {
  const count = records(coverage.fields).find((found) => found.field === field);
  return typeof count?.claims === "number" ? count.claims : null;
}
