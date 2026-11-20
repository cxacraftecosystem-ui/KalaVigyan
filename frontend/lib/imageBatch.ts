import { apiErrorMessage, apiFetch } from "@/lib/api";
import {
  declarationBody,
  declarationProblems,
  fileProblem,
  IMAGE_BATCH_PATH,
  imageContributionShape,
  uploadImageFile,
  type ImageContribution,
  type ImageOrigin
} from "@/lib/imageContributionContract";
import { list, parseShape } from "@/lib/shape";

export const BATCH_PICTURES_MAX = 10;

export type BatchWords = { caption: string; altText: string; prompt: string };
export type ImageBatchInput = { craftSlug: string; origin: ImageOrigin; generator: string; claimIds: string[]; pictures: BatchWords[] };
export type BatchSent = { sent: ImageContribution[]; problems: string[] };

const SHARED_FIELDS = ["craftSlug", "origin", "generator", "rightsConfirmed", "termsVersion"];
const PICTURE_FIELDS = ["claimIds", "prompt", "caption", "altText"];

export function emptyWords(): BatchWords {
  return { caption: "", altText: "", prompt: "" };
}

export function batchProblems(batch: ImageBatchInput, files: readonly File[]): string[] {
  return batch.pictures.flatMap((words, index) => {
    const found = declarationProblems({ ...batch, ...words, stageId: null });
    const chosen = files[index];
    const file = chosen ? fileProblem(chosen) : "Choose the picture.";
    return [...found, ...(file ? [file] : [])].map((problem) => `Picture ${index + 1}: ${problem}`);
  });
}

export function batchBody(batch: ImageBatchInput): Record<string, unknown> {
  const bodies = batch.pictures.map((words) => declarationBody({ ...batch, ...words, stageId: null }));
  const shared = Object.fromEntries(Object.entries(bodies[0] ?? {}).filter(([field]) => SHARED_FIELDS.includes(field)));
  return { ...shared, pictures: bodies.map((body) => Object.fromEntries(Object.entries(body).filter(([field]) => PICTURE_FIELDS.includes(field)))) };
}

export async function declareImages(batch: ImageBatchInput): Promise<ImageContribution[]> {
  const body = await apiFetch<unknown>(IMAGE_BATCH_PATH, { method: "POST", body: JSON.stringify(batchBody(batch)) });
  return parseShape(list(imageContributionShape, 1), body);
}

export async function sendBatch(batch: ImageBatchInput, files: readonly File[]): Promise<BatchSent> {
  const declared = await declareImages(batch);
  const sent: ImageContribution[] = [];
  const problems: string[] = [];
  for (const [index, row] of declared.entries()) {
    const file = files[index];
    if (!file) continue;
    try {
      sent.push(await uploadImageFile(row.id, file));
    } catch (cause) {
      problems.push(`Picture ${index + 1}: ${apiErrorMessage(cause, "Couldn't send it. Try again.")}`);
    }
  }
  return { sent, problems };
}
