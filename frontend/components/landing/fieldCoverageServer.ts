import { fieldHoldings, type FieldHoldings } from "@/components/landing/fieldHoldings";
import { isMonograph, readerCrafts } from "@/lib/atlasCollection";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";
import { MONOGRAPH_COVERAGE_PATH, monographCoverageShape, type FieldCoverage } from "@/lib/fieldCoverage";
import { craftPageTag, STATIC_FETCH_TIMEOUT_MS } from "@/lib/server/readingPages";
import { publicFetch } from "@/lib/server/serverFetch";
import { parseShape } from "@/lib/shape";

export function coveragesOf(read: readonly FieldCoverage[], slugs: readonly string[]): FieldCoverage[] | null {
  const bySlug = new Map(read.map((coverage) => [coverage.subjectSlug, coverage]));
  const found = slugs.map((slug) => bySlug.get(slug));
  return found.every((coverage): coverage is FieldCoverage => coverage !== undefined) ? found : null;
}

export async function serverCoverages(slugs: readonly string[]): Promise<FieldCoverage[] | null> {
  if (slugs.length === 0) return null;
  const result = await publicFetch(MONOGRAPH_COVERAGE_PATH, {
    parse: (body) => parseShape(monographCoverageShape, body),
    tags: slugs.map(craftPageTag),
    deps: { timeoutMs: STATIC_FETCH_TIMEOUT_MS }
  });
  return result.ok ? coveragesOf(result.body.crafts, slugs) : null;
}

export async function serverFieldHoldings(catalogue: CraftCatalogue | null): Promise<FieldHoldings | null> {
  if (!catalogue) return null;
  const slugs = readerCrafts(catalogue).filter(isMonograph).map((craft) => craft.slug);
  const coverages = await serverCoverages(slugs);
  return coverages ? fieldHoldings(coverages) : null;
}
