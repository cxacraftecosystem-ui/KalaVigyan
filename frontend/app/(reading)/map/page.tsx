import type { Metadata } from "next";

import { CraftsMapScreen } from "@/components/map/CraftsMapScreen";
import { serverCraftCatalogue } from "@/lib/server/readingPages";

export const metadata: Metadata = {
  title: "Map",
  description: "Where India's crafts are practised, state by state, with district soil, climate and land cover beside them."
};

export default async function MapPage() {
  return <CraftsMapScreen initial={await serverCraftCatalogue()} />;
}
