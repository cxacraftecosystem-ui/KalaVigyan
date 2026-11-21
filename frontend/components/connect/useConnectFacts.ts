"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { addressThroughSite, catalogueThroughSite } from "@/lib/connectFetch";
import type { ConnectFacts } from "@/lib/connectCatalogue";

export type ConnectFactsView = ConnectFacts;
export type ConnectFactsState = ConnectFacts & { failed: boolean; retry: () => void };

export function useConnectFacts(initial: ConnectFacts): ConnectFactsState {
  const [facts, setFacts] = useState(initial);
  const [failed, setFailed] = useState(false);
  const known = useRef(initial);

  const load = useCallback(async () => {
    try {
      const [address, catalogue] = await Promise.all([known.current.address ?? addressThroughSite(), known.current.catalogue ?? catalogueThroughSite()]);
      known.current = { address, catalogue };
      setFacts(known.current);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    if (!known.current.address || !known.current.catalogue) void load();
  }, [load]);

  const retry = () => {
    setFailed(false);
    void load();
  };

  return { ...facts, failed, retry };
}
