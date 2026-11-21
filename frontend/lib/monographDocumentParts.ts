export const DOCUMENT_PART_SCHEMA_VERSION = 1;
const CARRIED = ["specs", "fragments"] as const;

export type DocumentPart = { schemaVersion: typeof DOCUMENT_PART_SCHEMA_VERSION; version: number; part: number; parts: number; body: Record<string, unknown> };

export class DocumentPartError extends Error {}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function whole(raw: Record<string, unknown>): DocumentPart {
  return { schemaVersion: DOCUMENT_PART_SCHEMA_VERSION, version: typeof raw.version === "number" ? raw.version : 0, part: 0, parts: 1, body: raw };
}

export function documentPart(raw: unknown): DocumentPart {
  if (!isRecord(raw)) throw new DocumentPartError("A monograph part came back as something other than an object");
  if (!("parts" in raw) && !("part" in raw)) return whole(raw);
  const { schemaVersion, version, part, parts, body } = raw;
  const counted = typeof part === "number" && typeof parts === "number" && Number.isInteger(part) && Number.isInteger(parts) && part >= 0 && part < parts;
  if (schemaVersion !== DOCUMENT_PART_SCHEMA_VERSION || typeof version !== "number" || !counted || !isRecord(body)) {
    throw new DocumentPartError("A monograph part came back in another shape");
  }
  return { schemaVersion, version, part: part as number, parts: parts as number, body };
}

export function documentPartPath(path: string, part: number, version: number | null): string {
  const query = new URLSearchParams();
  if (version !== null) query.set("version", String(version));
  query.set("part", String(part));
  return `${path}?${query.toString()}`;
}

function joined(into: Record<string, unknown>, from: unknown): Record<string, unknown> {
  return { ...into, ...(isRecord(from) ? from : {}) };
}

export function joinedDocument(parts: readonly DocumentPart[]): Record<string, unknown> {
  const [first, ...later] = parts;
  if (!first || first.part !== 0) throw new DocumentPartError("A monograph is read from its first part");
  const document: Record<string, unknown> = { ...first.body };
  for (const field of CARRIED) document[field] = joined({}, first.body[field]);
  later.forEach((part, at) => {
    if (part.part !== at + 1 || part.parts !== first.parts || part.version !== first.version) throw new DocumentPartError(`Part ${at + 1} of monograph version ${first.version} came back from another reading`);
    if (Object.hasOwn(part.body, "shell")) document.shell = part.body.shell;
    for (const field of CARRIED) document[field] = joined(document[field] as Record<string, unknown>, part.body[field]);
  });
  if (later.length !== first.parts - 1) throw new DocumentPartError(`Monograph version ${first.version} has ${first.parts} parts, not ${later.length + 1}`);
  return document;
}
