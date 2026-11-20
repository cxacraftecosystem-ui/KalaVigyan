import type { Metadata } from "next";

import { CraftAtlas } from "@/components/crafts/CraftAtlas";
import { serverAtlasNames } from "@/lib/atlasNamesServer";
import { atlasMetadata } from "@/lib/readingMetadata";
import { serverCraftCatalogue } from "@/lib/server/readingPages";

export async function generateMetadata(): Promise<Metadata> {
  return atlasMetadata(await serverCraftCatalogue());
}

export default async function CraftsPage() {
  const initial = await serverCraftCatalogue();
  const names = await serverAtlasNames(initial);
  return <CraftAtlas initial={initial} names={names} />;
}
