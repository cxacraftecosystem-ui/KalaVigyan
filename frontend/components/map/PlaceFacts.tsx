"use client";

import { Droplets, Gem, Layers, Mountain, Sprout, Thermometer, Trees, type LucideIcon } from "lucide-react";

import { useCitations } from "@/components/answer/CitationContext";
import { EvidenceTag } from "@/components/editorial/EvidenceMark";
import { YearlySeriesRow } from "@/components/map/YearlySeriesRow";
import { sourceHref } from "@/lib/citations";
import { levelMark } from "@/lib/citationCluster";
import type { PlaceBasis, RegionDataset, RegionFacet, RegionFacetName } from "@/lib/regionContract";
import { datasetOf, FACET_LABEL, valueLabel, valueProvenance, valueReading } from "@/lib/regionView";
import { foldedRows } from "@/lib/yearlySeries";

const FACET_ICON: Record<RegionFacetName, LucideIcon> = {
  SOIL: Sprout,
  CLIMATE: Thermometer,
  WATER: Droplets,
  FOREST: Trees,
  LAND_COVER: Layers,
  TERRAIN: Mountain,
  GEOLOGY: Gem
};

const SOURCE_LINK = "text-ink-2 underline-offset-3 hover:text-indigo-hover hover:underline";

export function BasisLine({ basis }: { basis: PlaceBasis }) {
  const { numbers, sourcesById } = useCitations();
  const source = basis.sourceId ? sourcesById.get(basis.sourceId) : undefined;
  const href = source ? sourceHref(source) : null;
  const number = basis.sourceId ? numbers.get(basis.sourceId) : undefined;
  return (
    <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 font-ui text-caption text-ink-3" data-testid="place-basis">
      <span>Source:</span>
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className={SOURCE_LINK}>
          {basis.label}
        </a>
      ) : (
        <span className="text-ink-2">{basis.label}</span>
      )}
      {number ? <span className="tabular-nums lining-nums">[{number}]</span> : null}
      <EvidenceTag {...levelMark(basis.level)} />
    </p>
  );
}

export function FacetBlock({ facet, datasets }: { facet: RegionFacet; datasets: Map<string, RegionDataset> }) {
  const Icon = FACET_ICON[facet.facet];
  return (
    <section data-testid={`region-facet-${facet.facet}`}>
      <h4 className="field-label mb-2 flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5" aria-hidden />
        {FACET_LABEL[facet.facet]}
      </h4>
      <dl className="grid gap-3">
        {foldedRows(facet.values).map((row, index) =>
          row.kind === "series" ? (
            <YearlySeriesRow key={row.series.key} series={row.series} dataset={datasetOf(datasets, row.series.first.datasetCode)} />
          ) : (
            <div key={`${row.value.datasetCode}:${row.value.variable}:${row.value.depth ?? ""}:${row.value.period}:${row.value.stat}:${index}`} className="grid gap-0.5">
              <dt className="font-ui text-caption text-ink-3">{valueLabel(row.value)}</dt>
              <dd className="font-ui text-h4 tabular-nums lining-nums text-ink-1">{valueReading(row.value)}</dd>
              <dd className="font-ui text-caption text-ink-3">{valueProvenance(row.value, datasetOf(datasets, row.value.datasetCode))}</dd>
            </div>
          )
        )}
      </dl>
    </section>
  );
}
