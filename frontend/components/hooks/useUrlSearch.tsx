"use client";

import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";

export type UrlSearch = { params: URLSearchParams; known: boolean; reader: ReactNode };

function UrlSearchReader({ onSearch }: { onSearch: (search: string) => void }) {
  const search = useSearchParams().toString();
  useEffect(() => onSearch(search), [search, onSearch]);
  return null;
}

export function useUrlSearch(): UrlSearch {
  const [search, setSearch] = useState<string | null>(null);
  const params = useMemo(() => new URLSearchParams(search ?? ""), [search]);
  const reader = (
    <Suspense fallback={null}>
      <UrlSearchReader onSearch={setSearch} />
    </Suspense>
  );
  return { params, known: search !== null, reader };
}
