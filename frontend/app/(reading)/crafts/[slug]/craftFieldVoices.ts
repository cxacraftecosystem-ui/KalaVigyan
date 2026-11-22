import { cache } from "react";

import { FIELD_VOICES_PATH, fieldVoicesListShape, type FieldListKind, type FieldVoicesList } from "@/lib/fieldVoicesContract";
import type { FieldVoicesFirst } from "@/lib/fieldVoicesView";
import { craftPageTag, STATIC_FETCH_TIMEOUT_MS } from "@/lib/server/readingPages";
import { publicFetch } from "@/lib/server/serverFetch";
import { parseShape } from "@/lib/shape";
import { STATIC_PAGE_REVALIDATE_SECONDS } from "@/lib/sitePagesContract";

export const FIELD_VOICES_UNAVAILABLE = "The craft's field voices could not be read";
const NOT_FOUND = 404;

async function firstPage(slug: string, kind: FieldListKind): Promise<FieldVoicesList | null> {
  const result = await publicFetch(FIELD_VOICES_PATH(slug, kind, null), {
    parse: (body) => parseShape(fieldVoicesListShape, body),
    tags: [craftPageTag(slug)],
    revalidateSeconds: STATIC_PAGE_REVALIDATE_SECONDS,
    deps: { timeoutMs: STATIC_FETCH_TIMEOUT_MS }
  });
  if (result.ok) return result.body;
  if (result.status === NOT_FOUND) return null;
  throw new Error(`${FIELD_VOICES_UNAVAILABLE}: ${result.failure}`);
}

export const craftFieldVoices = cache(async (slug: string): Promise<FieldVoicesFirst | null> => {
  const [quotes, images] = await Promise.all([firstPage(slug, "quotes"), firstPage(slug, "images")]);
  return quotes && images ? { quotes, images } : null;
});
