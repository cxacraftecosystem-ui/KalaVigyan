import { fieldHoldings, type FieldHoldings } from "@/components/landing/fieldHoldings";
import { isMonograph, readerCrafts } from "@/lib/atlasCollection";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";
import { fieldCoverageShape, type FieldCoverage } from "@/lib/fieldCoverage";
import { craftPageTag, STATIC_FETCH_TIMEOUT_MS } from "@/lib/server/readingPages";
import { publicFetch } from "@/lib/server/serverFetch";
import { parseShape } from "@/lib/shape";

export const COVERAGE_BATCH = 6;

export const coveragePath = (slug: string) => `/crafts/${encodeURIComponent(slug)}/coverage`;

export function batches<T>(items: readonly T[], size: number): T[][] {
  const out: T[][] = [];
  for (let at = 0; at < items.length; at += size) out.push(items.slice(at, at + size));
  return out;
}

async function coverageOf(slug: string): Promise<FieldCoverage | null> {
  const result = await publicFetch(coveragePath(slug), { parse: (body) => parseShape(fieldCoverageShape, body), tags: [craftPageTag(slug)], deps: { timeoutMs: STATIC_FETCH_TIMEOUT_MS } });
  return result.ok ? result.body : null;
}

export async function serverCoverages(slugs: readonly string[]): Promise<FieldCoverage[] | null> {
  if (slugs.length === 0) return null;
  const read: FieldCoverage[] = [];
  for (const batch of batches(slugs, COVERAGE_BATCH)) {
    const found = (await Promise.all(batch.map(coverageOf))).filter((coverage): coverage is FieldCoverage => coverage !== null);
    if (found.length < batch.length) return null;
    read.push(...found);
  }
  return read;
}

export async function serverFieldHoldings(catalogue: CraftCatalogue | null): Promise<FieldHoldings | null> {
  if (!catalogue) return null;
  const slugs = readerCrafts(catalogue).filter(isMonograph).map((craft) => craft.slug);
  const coverages = await serverCoverages(slugs);
  return coverages ? fieldHoldings(coverages) : null;
}
