import { apiFetch } from "@/lib/api";
import { OPEN_DATA_PATH, parseOpenDataListing, type OpenDataListing } from "@/lib/openDataContract";

export async function fetchOpenData(): Promise<OpenDataListing> {
  return parseOpenDataListing(await apiFetch<unknown>(OPEN_DATA_PATH, {}, { revalidateFromHttpCache: true }));
}
