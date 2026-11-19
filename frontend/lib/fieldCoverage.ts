import { DISCIPLINES, type Discipline } from "@/lib/explainerBlockBase";
import { integer, list, matching, object, oneOf, text, type Shape } from "@/lib/shape";

export const FIELD_STANDINGS = ["COVERED", "THIN", "MISSING"] as const;
export const COVERAGE_SUBJECT_KINDS = ["craft", "family", "category"] as const;

export type FieldStanding = (typeof FIELD_STANDINGS)[number];

export type FieldCount = {
  field: Discipline;
  claims: number;
  structureClaims: number;
  sources: number;
  sections: number;
  sentences: number;
  figures: number;
  standing: FieldStanding;
};

export type FieldCoverage = {
  schemaVersion: 1;
  subjectKind: (typeof COVERAGE_SUBJECT_KINDS)[number];
  subjectSlug: string;
  name: string;
  claimsMin: number;
  claims: number;
  sources: number;
  covered: Discipline[];
  thin: Discipline[];
  missing: Discipline[];
  fields: FieldCount[];
};

const field = oneOf(DISCIPLINES);

const fieldCountShape: Shape<FieldCount> = object<FieldCount>({
  field,
  claims: integer,
  structureClaims: integer,
  sources: integer,
  sections: integer,
  sentences: integer,
  figures: integer,
  standing: oneOf(FIELD_STANDINGS)
});

export const fieldCoverageShape: Shape<FieldCoverage> = object<FieldCoverage>({
  schemaVersion: oneOf([1] as const),
  subjectKind: oneOf(COVERAGE_SUBJECT_KINDS),
  subjectSlug: matching(/^[A-Za-z0-9-]+$/, "a subject slug"),
  name: text,
  claimsMin: integer,
  claims: integer,
  sources: integer,
  covered: list(field),
  thin: list(field),
  missing: list(field),
  fields: list(fieldCountShape, DISCIPLINES.length)
});
