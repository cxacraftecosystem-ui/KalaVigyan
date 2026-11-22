import { apiFetch } from "@/lib/api";
import { OPEN_DATA_PATH, parseOpenDataListing, type OpenDataListing } from "@/lib/openDataContract";

let shared: Promise<OpenDataListing | null> | null = null;

export async function fetchOpenData(): Promise<OpenDataListing> {
  return parseOpenDataListing(await apiFetch<unknown>(OPEN_DATA_PATH, {}, { revalidateFromHttpCache: true }));
}

export function sharedOpenData(load: () => Promise<OpenDataListing> = fetchOpenData): Promise<OpenDataListing | null> {
  shared ??= load().catch(() => {
    shared = null;
    return null;
  });
  return shared;
}
