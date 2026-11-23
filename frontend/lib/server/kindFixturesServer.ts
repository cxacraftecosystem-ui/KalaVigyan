import { cache } from "react";

import { KIND_FIXTURES_PATH, parseKindFixtures, type KindFixture } from "@/lib/kindFixtures";
import { bodyOrAbsent, publicFetch } from "@/lib/server/serverFetch";
import { STATIC_PAGE_REVALIDATE_SECONDS } from "@/lib/sitePagesContract";

export const KIND_FIXTURES_TAG = "kind-fixtures";
const UNAVAILABLE = "The kind fixtures could not be read";

export const serverKindFixtures = cache(async (): Promise<KindFixture[] | null> => {
  const result = await publicFetch(KIND_FIXTURES_PATH, { parse: parseKindFixtures, tags: [KIND_FIXTURES_TAG], revalidateSeconds: STATIC_PAGE_REVALIDATE_SECONDS });
  return bodyOrAbsent(result, UNAVAILABLE);
});
