import { cache } from "react";

import { CRAFT_PAGE_PATH, checkedCraftPage, craftPageShape, type CraftPage } from "@/lib/craftPageContract";
import { craftPageTag, STATIC_FETCH_TIMEOUT_MS } from "@/lib/server/readingPages";
import { publicFetch } from "@/lib/server/serverFetch";
import { parseShape } from "@/lib/shape";
import { STATIC_PAGE_REVALIDATE_SECONDS } from "@/lib/sitePagesContract";

export const CRAFT_RECORD_UNAVAILABLE = "The craft's record could not be read";
const NOT_FOUND = 404;

export const craftRecordPage = cache(async (slug: string): Promise<CraftPage | null> => {
  const result = await publicFetch(CRAFT_PAGE_PATH(slug), {
    parse: (body) => checkedCraftPage(parseShape(craftPageShape, body)),
    tags: [craftPageTag(slug)],
    revalidateSeconds: STATIC_PAGE_REVALIDATE_SECONDS,
    deps: { timeoutMs: STATIC_FETCH_TIMEOUT_MS }
  });
  if (result.ok) return result.body;
  if (result.status === NOT_FOUND) return null;
  throw new Error(`${CRAFT_RECORD_UNAVAILABLE}: ${result.failure}`);
});
