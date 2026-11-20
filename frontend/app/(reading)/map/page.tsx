import type { Metadata } from "next";
import { Suspense } from "react";

import { CraftsMapScreen } from "@/components/map/CraftsMapScreen";
import { Skeleton } from "@/components/ui/Skeleton";
import { serverCraftCatalogue } from "@/lib/server/readingPages";

export const metadata: Metadata = {
  title: "Map",
  description: "Where India's crafts are practised, state by state, with district soil, climate and land cover beside them."
};

export default async function MapPage() {
  const initial = await serverCraftCatalogue();
  return (
    <Suspense fallback={<Skeleton shape="chart" label="Drawing the map" />}>
      <CraftsMapScreen initial={initial} />
    </Suspense>
  );
}
