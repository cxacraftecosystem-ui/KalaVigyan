import { cache } from "react";

import { FIELD_VOICES_PATH, fieldVoicesListShape, type FieldListKind, type FieldVoicesList } from "@/lib/fieldVoicesContract";
import type { FieldVoicesFirst } from "@/lib/fieldVoicesView";
import { craftPageTag, STATIC_FETCH_TIMEOUT_MS } from "@/lib/server/readingPages";
import { publicFetch } from "@/lib/server/serverFetch";
import { parseShape } from "@/lib/shape";
import { STATIC_PAGE_REVALIDATE_SECONDS } from "@/lib/sitePagesContract";

async function firstPage(slug: string, kind: FieldListKind): Promise<FieldVoicesList | null> {
  const result = await publicFetch(FIELD_VOICES_PATH(slug, kind, null), {
    parse: (body) => parseShape(fieldVoicesListShape, body),
    tags: [craftPageTag(slug)],
    revalidateSeconds: STATIC_PAGE_REVALIDATE_SECONDS,
    deps: { timeoutMs: STATIC_FETCH_TIMEOUT_MS }
  });
  return result.ok ? result.body : null;
}

export const craftFieldVoices = cache(async (slug: string): Promise<FieldVoicesFirst | null> => {
  const [quotes, images] = await Promise.all([firstPage(slug, "quotes"), firstPage(slug, "images")]);
  return quotes && images ? { quotes, images } : null;
});
