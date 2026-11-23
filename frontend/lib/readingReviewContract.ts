import { list, nullable, number, object, text, type Shape } from "@/lib/shape";
import { sourceShape, type FactSource } from "@/lib/reviewSources";

export type ReadingReview = {
  stated: string;
  quantity: string;
  unit: string;
  min: number | null;
  max: number | null;
  envelopeMin: number | null;
  envelopeMax: number | null;
  condition: string;
  stage: string;
  stageType: string;
  claimId: string;
  statement: string;
  sources: FactSource[];
};

export const readingShape: Shape<ReadingReview> = object<ReadingReview>({
  stated: text,
  quantity: text,
  unit: text,
  min: nullable(number),
  max: nullable(number),
  envelopeMin: nullable(number),
  envelopeMax: nullable(number),
  condition: text,
  stage: text,
  stageType: text,
  claimId: text,
  statement: text,
  sources: list(sourceShape)
});
