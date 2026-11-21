import { boolean, dictionary, integer, list, matching, nullable, object, oneOf, parseShape, text, type Shape } from "@/lib/shape";

export const OPEN_DATA_PATH = "/open-data";
export const OPEN_DATA_SCHEMA_VERSION = 1;
export const OPEN_DATA_REVALIDATE_SECONDS = 300;

const TABLE_NAME = /^[a-z_]+$/;
const DAY = matching(/^\d{4}-\d{2}-\d{2}$/, "a day as YYYY-MM-DD");
const HTTPS = matching(/^https:\/\/\S+$/, "an https address");

export type ReleaseFile = { path: string; bytes: number; downloadUrl: string };
export type ChangeCounts = { added: number; removed: number; changed: number };
export type PublishedRelease = {
  version: string;
  releasedOn: string;
  doi: string;
  doiUrl: string;
  recordUrl: string;
  publishedAt: string;
  totalBytes: number;
  files: ReleaseFile[];
  counts: Record<string, number>;
  changes: Record<string, ChangeCounts>;
  citation: string;
  bibtex: string;
};
export type DatasetField = { name: string; type: string; description: string; required: boolean };
export type DatasetTable = { name: string; title: string; description: string; key: string[]; files: string[]; fields: DatasetField[] };
export type DatasetLicence = { id: string; name: string; url: string };
export type OpenDataListing = {
  schemaVersion: typeof OPEN_DATA_SCHEMA_VERSION;
  title: string;
  summary: string;
  creator: string;
  licence: DatasetLicence;
  attribution: string;
  citedWorks: string;
  leftOut: string[];
  codeUrl: string;
  pageUrl: string;
  conceptDoi: string | null;
  conceptDoiUrl: string | null;
  citation: string;
  bibtex: string;
  latest: PublishedRelease | null;
  releases: PublishedRelease[];
  tables: DatasetTable[];
};

const changeCountsShape: Shape<ChangeCounts> = object({ added: integer, removed: integer, changed: integer });

const releaseShape: Shape<PublishedRelease> = object({
  version: matching(/^\d{4}\.\d{2}\.\d{2}(\.\d{1,2})?$/, "a release version"),
  releasedOn: DAY,
  doi: text,
  doiUrl: HTTPS,
  recordUrl: HTTPS,
  publishedAt: text,
  totalBytes: integer,
  files: list(object<ReleaseFile>({ path: text, bytes: integer, downloadUrl: HTTPS })),
  counts: dictionary(TABLE_NAME, integer),
  changes: dictionary(TABLE_NAME, changeCountsShape),
  citation: text,
  bibtex: text
});

const tableShape: Shape<DatasetTable> = object({
  name: matching(TABLE_NAME, "a table name"),
  title: text,
  description: text,
  key: list(text, 1),
  files: list(text),
  fields: list(object<DatasetField>({ name: text, type: text, description: text, required: boolean }), 1)
});

const listingShape: Shape<OpenDataListing> = object({
  schemaVersion: oneOf([OPEN_DATA_SCHEMA_VERSION] as const),
  title: text,
  summary: text,
  creator: text,
  licence: object<DatasetLicence>({ id: text, name: text, url: HTTPS }),
  attribution: text,
  citedWorks: text,
  leftOut: list(text),
  codeUrl: HTTPS,
  pageUrl: text,
  conceptDoi: nullable(text),
  conceptDoiUrl: nullable(HTTPS),
  citation: text,
  bibtex: text,
  latest: nullable(releaseShape),
  releases: list(releaseShape),
  tables: list(tableShape, 1)
});

export function parseOpenDataListing(raw: unknown): OpenDataListing {
  return parseShape(listingShape, raw);
}
