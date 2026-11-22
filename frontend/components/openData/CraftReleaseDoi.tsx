"use client";

import { useEffect, useState } from "react";

import { CraftReleaseLine } from "@/components/openData/CraftReleaseLine";
import { sharedOpenData } from "@/lib/openData";
import type { CraftRelease } from "@/lib/openDataContract";
import { craftOfPage, craftReleaseFor } from "@/lib/openDataCrafts";

export function CraftReleaseDoi({ pageUrl }: { pageUrl: string }) {
  const [release, setRelease] = useState<CraftRelease | null>(null);
  useEffect(() => {
    if (craftOfPage(pageUrl) === null) return;
    let live = true;
    void sharedOpenData().then((listing) => {
      if (live) setRelease(craftReleaseFor(listing, pageUrl));
    });
    return () => {
      live = false;
    };
  }, [pageUrl]);
  return release ? <CraftReleaseLine release={release} /> : null;
}
