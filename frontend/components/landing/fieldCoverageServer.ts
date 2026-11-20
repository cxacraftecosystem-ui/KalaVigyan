import { fieldHoldings, type FieldHoldings } from "@/components/landing/fieldHoldings";
import { isMonograph, readerCrafts } from "@/lib/atlasCollection";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";
import { fieldCoverageShape, type FieldCoverage } from "@/lib/fieldCoverage";
import { craftPageTag } from "@/lib/server/readingPages";
import { publicFetch } from "@/lib/server/serverFetch";
import { parseShape } from "@/lib/shape";

export const coveragePath = (slug: string) => `/crafts/${encodeURIComponent(slug)}/coverage`;

export async function serverCoverages(slugs: readonly string[]): Promise<FieldCoverage[] | null> {
  if (slugs.length === 0) return null;
  const results = await Promise.all(slugs.map((slug) => publicFetch(coveragePath(slug), { parse: (body) => parseShape(fieldCoverageShape, body), tags: [craftPageTag(slug)] })));
  const read = results.flatMap((result) => (result.ok ? [result.body] : []));
  return read.length === slugs.length ? read : null;
}

export async function serverFieldHoldings(catalogue: CraftCatalogue | null): Promise<FieldHoldings | null> {
  if (!catalogue) return null;
  const slugs = readerCrafts(catalogue).filter(isMonograph).map((craft) => craft.slug);
  const coverages = await serverCoverages(slugs);
  return coverages ? fieldHoldings(coverages) : null;
}
