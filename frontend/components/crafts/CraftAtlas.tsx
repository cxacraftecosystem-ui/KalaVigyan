"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AtlasCollection } from "@/components/crafts/AtlasCollection";
import { AtlasIndex } from "@/components/crafts/AtlasIndex";
import { AtlasResults, AtlasSearchBox } from "@/components/crafts/AtlasSearch";
import { ledFamilyShelves } from "@/components/crafts/shelfLead";
import { useUrlSearch } from "@/components/hooks/useUrlSearch";
import { MapRetry } from "@/components/map/MapRetry";
import { Skeleton } from "@/components/ui/Skeleton";
import { atlasDek, stateCounts } from "@/lib/atlasIndex";
import type { NamedCraft } from "@/lib/atlasNames";
import { useCraftCatalogue } from "@/lib/craftCatalogue";
import type { CraftCatalogue } from "@/lib/craftCatalogueContract";

export const ATLAS_HEADING = "The atlas";
const QUERY_PARAM = "q";
const WRITE_DELAY_MS = 300;

export function CraftAtlasHeader({ dek, search }: { dek?: string | null; search?: ReactNode }) {
  return (
    <header className="grid grid-cols-1 gap-6 pt-8 pb-7 md:pt-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,6fr)] lg:items-end lg:gap-16">
      <div className="min-w-0">
        <h1 className="font-headline text-h1 text-ink-1">{ATLAS_HEADING}</h1>
        {dek ? <p className="mt-[18px] max-w-[44ch] font-reading text-body text-ink-2">{dek}</p> : null}
      </div>
      {search}
    </header>
  );
}

function useQueryParam(): [string, (next: string) => void, ReactNode] {
  const { params, known, reader } = useUrlSearch();
  const router = useRouter();
  const pathname = usePathname();
  const fromUrl = params.get(QUERY_PARAM) ?? "";
  const [query, setQuery] = useState("");
  const written = useRef<string | null>(null);

  useEffect(() => {
    if (!known || fromUrl === written.current) return;
    written.current = fromUrl;
    setQuery(fromUrl);
  }, [fromUrl, known]);

  useEffect(() => {
    const next = query.trim();
    if (written.current === null || next === written.current) return;
    const timer = setTimeout(() => {
      written.current = next;
      router.replace(next ? `${pathname}?${QUERY_PARAM}=${encodeURIComponent(next)}` : pathname, { scroll: false });
    }, WRITE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [pathname, query, router]);

  return [query, setQuery, reader];
}

function AtlasBody({ catalogue, names, query, onQuery }: { catalogue: CraftCatalogue; names: readonly NamedCraft[]; query: string; onQuery: (next: string) => void }) {
  const shelves = useMemo(() => ledFamilyShelves(catalogue), [catalogue]);
  const counts = useMemo(() => stateCounts(catalogue), [catalogue]);
  return (
    <>
      <AtlasResults catalogue={catalogue} query={query} onQuery={onQuery} />
      <AtlasIndex catalogue={catalogue} counts={counts} />
      <AtlasCollection shelves={shelves} names={names} />
    </>
  );
}

export function CraftAtlas({ initial, names }: { initial: CraftCatalogue | null; names: readonly NamedCraft[] }) {
  const { catalogue: loaded, error, reload } = useCraftCatalogue();
  const catalogue = loaded ?? initial;
  const [query, setQuery, urlReader] = useQueryParam();
  const search = <AtlasSearchBox catalogue={catalogue} query={query} onQuery={setQuery} />;
  return (
    <div className="pb-section" data-testid="craft-atlas">
      {urlReader}
      <CraftAtlasHeader dek={catalogue ? atlasDek(catalogue) : null} search={search} />
      {catalogue ? (
        <AtlasBody catalogue={catalogue} names={names} query={query} onQuery={setQuery} />
      ) : error ? (
        <MapRetry message={`${error} Try again in a moment.`} onRetry={reload} />
      ) : (
        <Skeleton shape="plateGrid" label="Opening the collection" />
      )}
    </div>
  );
}
