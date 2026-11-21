export const DOCUMENT_PART_SCHEMA_VERSION = 1;
const CARRIED = ["specs", "fragments"] as const;

export type DocumentPart = { schemaVersion: typeof DOCUMENT_PART_SCHEMA_VERSION; version: number; part: number; parts: number; tag: string | null; body: Record<string, unknown> };
export type PartRead = { version: number | null; language: string | null; tag: string | null };

export const LATEST_READ: PartRead = { version: null, language: null, tag: null };

export class DocumentPartError extends Error {}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function whole(raw: Record<string, unknown>): DocumentPart {
  return { schemaVersion: DOCUMENT_PART_SCHEMA_VERSION, version: typeof raw.version === "number" ? raw.version : 0, part: 0, parts: 1, tag: null, body: raw };
}

export function documentPart(raw: unknown): DocumentPart {
  if (!isRecord(raw)) throw new DocumentPartError("A monograph part came back as something other than an object");
  if (!("parts" in raw) && !("part" in raw)) return whole(raw);
  const { schemaVersion, version, part, parts, tag = null, body } = raw;
  const counted = typeof part === "number" && typeof parts === "number" && Number.isInteger(part) && Number.isInteger(parts) && part >= 0 && part < parts;
  const tagged = tag === null || typeof tag === "string";
  if (schemaVersion !== DOCUMENT_PART_SCHEMA_VERSION || typeof version !== "number" || !counted || !tagged || !isRecord(body)) {
    throw new DocumentPartError("A monograph part came back in another shape");
  }
  return { schemaVersion, version, part: part as number, parts: parts as number, tag: tag as string | null, body };
}

export function documentPartPath(path: string, part: number, read: PartRead): string {
  const query = new URLSearchParams();
  if (read.language !== null) query.set("lang", read.language);
  if (read.version !== null) query.set("version", String(read.version));
  if (read.tag !== null) query.set("tag", read.tag);
  query.set("part", String(part));
  return `${path}?${query.toString()}`;
}

export function laterRead(first: DocumentPart, language: string | null): PartRead {
  return { version: first.version, language, tag: first.tag };
}

function joined(into: Record<string, unknown>, from: unknown): Record<string, unknown> {
  return { ...into, ...(isRecord(from) ? from : {}) };
}

function sameReading(part: DocumentPart, first: DocumentPart): boolean {
  return part.parts === first.parts && part.version === first.version && part.tag === first.tag;
}

export function joinedDocument(parts: readonly DocumentPart[]): Record<string, unknown> {
  const [first, ...later] = parts;
  if (!first || first.part !== 0) throw new DocumentPartError("A monograph is read from its first part");
  const document: Record<string, unknown> = { ...first.body };
  for (const field of CARRIED) document[field] = joined({}, first.body[field]);
  later.forEach((part, at) => {
    if (part.part !== at + 1 || !sameReading(part, first)) throw new DocumentPartError(`Part ${at + 1} of monograph version ${first.version} came back from another reading`);
    if (Object.hasOwn(part.body, "shell")) document.shell = part.body.shell;
    for (const field of CARRIED) document[field] = joined(document[field] as Record<string, unknown>, part.body[field]);
  });
  if (later.length !== first.parts - 1) throw new DocumentPartError(`Monograph version ${first.version} has ${first.parts} parts, not ${later.length + 1}`);
  return document;
}
