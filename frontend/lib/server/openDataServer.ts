import { cache } from "react";

import { OPEN_DATA_PATH, OPEN_DATA_REVALIDATE_SECONDS, parseOpenDataListing, type OpenDataListing } from "@/lib/openDataContract";
import { publicFetch } from "@/lib/server/serverFetch";

export const OPEN_DATA_TAG = "open-data";

export const serverOpenData = cache(async (): Promise<OpenDataListing | null> => {
  const result = await publicFetch(OPEN_DATA_PATH, { parse: parseOpenDataListing, tags: [OPEN_DATA_TAG], revalidateSeconds: OPEN_DATA_REVALIDATE_SECONDS });
  return result.ok ? result.body : null;
});
