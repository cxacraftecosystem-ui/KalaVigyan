import { craftLinkShape, HTTPS_URL, INSTANT, UUID, type CraftLink } from "@/lib/answerShapes";
import { apiFetch } from "@/lib/api";
import { boolean, integer, list, matching, nullable, number, object, oneOf, parseShape, ShapeError, text, type Shape } from "@/lib/shape";

export const MEDIA_JOBS_PATH = "/media/jobs";
export const MEDIA_JOB_PATH = (id: string) => `/media/jobs/${encodeURIComponent(id)}`;
export const MEDIA_OPTIONS_PATH = (slug: string) => `/media/options?craftSlug=${encodeURIComponent(slug)}`;

export const MEDIA_KINDS = ["IMAGE", "VIDEO"] as const;
export const MEDIA_JOB_STATUSES = ["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "BLOCKED"] as const;
export const OPEN_JOB_STATUSES: readonly MediaJobStatus[] = ["QUEUED", "RUNNING"];
export const ASSET_LABEL = "AI illustration";
export const STYLE_HINT_MAX_CHARS = 120;
export const IDEMPOTENCY_KEY_PATTERN = /^[A-Za-z0-9._:-]{16,160}$/;

export type MediaKind = (typeof MEDIA_KINDS)[number];
export type MediaJobStatus = (typeof MEDIA_JOB_STATUSES)[number];
export type MediaJobRequest = { kind: MediaKind; stageId: string; idempotencyKey: string; styleHint: string | null };
export type MediaLabel = { text: typeof ASSET_LABEL; model: string; generatedOn: string };
export type MediaAsset = {
  id: string;
  mime: "image/png" | "video/mp4";
  width: number;
  height: number;
  durationSeconds: number | null;
  url: string;
  urlExpiresAt: string;
  fileName: string;
  label: MediaLabel;
  altText: string;
  visibility: "PRIVATE" | "CRAFT_SHARED";
};
export type MediaJob = {
  id: string;
  kind: MediaKind;
  status: MediaJobStatus;
  craft: CraftLink;
  stage: { id: string; ordinal: number; name: string };
  claimIds: string[];
  cached: boolean;
  attempts: number;
  refunded: boolean;
  pollAfterSeconds: number | null;
  createdAt: string;
  updatedAt: string;
  asset: MediaAsset | null;
  failure: { reason: "FAILED" | "BLOCKED"; message: string } | null;
};
export type MediaKindOffer = { kind: MediaKind; remainingToday: number | null };
export type MediaOptions = {
  craft: CraftLink;
  kinds: MediaKindOffer[];
  stages: { stageId: string; kinds: MediaKind[] }[];
};

export const MEDIA_OUTPUT_MIME: Record<MediaKind, MediaAsset["mime"]> = { IMAGE: "image/png", VIDEO: "video/mp4" };
const FILE_ENTITY: Record<MediaKind, string> = { IMAGE: "KalaVigyan_Generated-Image_", VIDEO: "KalaVigyan_Generated-Video_" };

const KIND = oneOf(MEDIA_KINDS);

export const mediaAssetShape: Shape<MediaAsset> = object<MediaAsset>({
  id: UUID,
  mime: oneOf(["image/png", "video/mp4"] as const),
  width: integer,
  height: integer,
  durationSeconds: nullable(number),
  url: HTTPS_URL,
  urlExpiresAt: INSTANT,
  fileName: matching(/^KalaVigyan_Generated-(Image|Video)_[A-Za-z0-9_-]+_Step-\d{2}\.(png|mp4)$/, "a KalaVigyan media file name"),
  label: object<MediaLabel>({ text: oneOf([ASSET_LABEL] as const), model: text, generatedOn: matching(/^\d{4}-\d{2}-\d{2}$/, "a date") }),
  altText: text,
  visibility: oneOf(["PRIVATE", "CRAFT_SHARED"] as const),
});

export const mediaJobShape: Shape<MediaJob> = object<MediaJob>({
  id: UUID,
  kind: KIND,
  status: oneOf(MEDIA_JOB_STATUSES),
  craft: craftLinkShape,
  stage: object<{ id: string; ordinal: number; name: string }>({ id: UUID, ordinal: integer, name: text }),
  claimIds: list(UUID, 2),
  cached: boolean,
  attempts: integer,
  refunded: boolean,
  pollAfterSeconds: nullable(integer),
  createdAt: INSTANT,
  updatedAt: INSTANT,
  asset: nullable(mediaAssetShape),
  failure: nullable(object<{ reason: "FAILED" | "BLOCKED"; message: string }>({ reason: oneOf(["FAILED", "BLOCKED"] as const), message: text }))
});

export const mediaOptionsShape: Shape<MediaOptions> = object<MediaOptions>({
  craft: craftLinkShape,
  kinds: list(object<MediaKindOffer>({ kind: KIND, remainingToday: nullable(integer) })),
  stages: list(object<{ stageId: string; kinds: MediaKind[] }>({ stageId: UUID, kinds: list(KIND, 1) }))
});

function distinct(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

export function checkedMediaOptions(options: MediaOptions, craftSlug: string): MediaOptions {
  if (options.craft.slug !== craftSlug) throw new ShapeError("craft.slug", craftSlug);
  const offered = options.kinds.map((entry) => entry.kind);
  if (!distinct(offered)) throw new ShapeError("kinds", "each kind once");
  const exhausted = options.kinds.find((entry) => entry.remainingToday !== null && entry.remainingToday < 1);
  if (exhausted) throw new ShapeError(`kinds.${exhausted.kind}.remainingToday`, "a unit left or no daily limit");
  if (!distinct(options.stages.map((stage) => stage.stageId))) throw new ShapeError("stages", "each stage once");
  for (const stage of options.stages) {
    if (!distinct(stage.kinds) || !stage.kinds.every((kind) => offered.includes(kind))) {
      throw new ShapeError(`stages.${stage.stageId}.kinds`, "kinds the asker may still make, each once");
    }
  }
  return options;
}

export function checkedMediaAsset(asset: MediaAsset, kind: MediaKind): MediaAsset {
  if (asset.mime !== MEDIA_OUTPUT_MIME[kind] || !asset.fileName.startsWith(FILE_ENTITY[kind])) {
    throw new ShapeError(`asset ${asset.id}.mime`, `a ${MEDIA_OUTPUT_MIME[kind]} named for its kind`);
  }
  if ((asset.durationSeconds === null) !== (kind === "IMAGE")) throw new ShapeError(`asset ${asset.id}.durationSeconds`, "a duration for a video only");
  return asset;
}

export function checkedMediaJob(job: MediaJob): MediaJob {
  if ((job.asset !== null) !== (job.status === "SUCCEEDED")) throw new ShapeError(`job ${job.id}.asset`, "an asset exactly when the job succeeded");
  if (job.asset) checkedMediaAsset(job.asset, job.kind);
  const ended = job.status === "FAILED" || job.status === "BLOCKED" ? job.status : null;
  if ((job.failure?.reason ?? null) !== ended) throw new ShapeError(`job ${job.id}.failure`, "a reason exactly when the job failed or was blocked");
  const open = OPEN_JOB_STATUSES.includes(job.status);
  if (open !== (job.pollAfterSeconds !== null) || (job.pollAfterSeconds !== null && job.pollAfterSeconds < 1)) {
    throw new ShapeError(`job ${job.id}.pollAfterSeconds`, "a poll interval exactly while the job is open");
  }
  return job;
}

export async function fetchMediaOptions(craftSlug: string): Promise<MediaOptions> {
  return checkedMediaOptions(parseShape(mediaOptionsShape, await apiFetch<unknown>(MEDIA_OPTIONS_PATH(craftSlug))), craftSlug);
}

export async function createMediaJob(request: MediaJobRequest): Promise<MediaJob> {
  if (!IDEMPOTENCY_KEY_PATTERN.test(request.idempotencyKey)) throw new ShapeError("idempotencyKey", "16 to 160 of A-Z a-z 0-9 . _ : -");
  const body = await apiFetch<unknown>(MEDIA_JOBS_PATH, { method: "POST", body: JSON.stringify(request) });
  return checkedMediaJob(parseShape(mediaJobShape, body));
}

export async function fetchMediaJob(jobId: string): Promise<MediaJob> {
  return checkedMediaJob(parseShape(mediaJobShape, await apiFetch<unknown>(MEDIA_JOB_PATH(jobId))));
}

export function offeredKinds(options: MediaOptions, stageId: string): MediaKindOffer[] {
  const stage = options.stages.find((entry) => entry.stageId === stageId);
  if (!stage) return [];
  return MEDIA_KINDS.flatMap((kind) => {
    const offer = options.kinds.find((entry) => entry.kind === kind);
    return offer && stage.kinds.includes(kind) && offer.remainingToday !== 0 ? [offer] : [];
  });
}

export function offeredStageIds(options: MediaOptions, kind: MediaKind): Set<string> {
  return new Set(options.stages.filter((stage) => offeredKinds(options, stage.stageId).some((entry) => entry.kind === kind)).map((stage) => stage.stageId));
}
