import { cache } from "react";

import type { MonographDocument } from "@/lib/monographDocument";
import { parseMonographDocument } from "@/lib/monographDocumentShape";
import { signedInFetch } from "@/lib/server/serverFetch";

export const PREVIEW_TOKEN = /^[0-9a-f]{32}\.\d{1,12}\.[0-9a-f]{64}$/;
export const PREVIEW_UNAVAILABLE = "The preview could not be read";

export type PreviewRead = { kind: "shown"; document: MonographDocument } | { kind: "signed-out" } | { kind: "missing" };

const SIGNED_OUT = 401;
const HIDDEN = new Set([403, 404, 422]);

export function previewApiPath(token: string): string {
  return `/knowledge/pages/previews/${encodeURIComponent(token)}`;
}

export function previewPagePath(token: string): string {
  return `/preview/${encodeURIComponent(token)}`;
}

export const previewDocument = cache(async (token: string): Promise<PreviewRead> => {
  if (!PREVIEW_TOKEN.test(token)) return { kind: "missing" };
  const result = await signedInFetch(previewApiPath(token), { parse: parseMonographDocument });
  if (result.ok) return { kind: "shown", document: result.body };
  if (result.status === SIGNED_OUT) return { kind: "signed-out" };
  if (result.status !== null && HIDDEN.has(result.status)) return { kind: "missing" };
  throw new Error(`${PREVIEW_UNAVAILABLE}: ${result.failure}`);
});
