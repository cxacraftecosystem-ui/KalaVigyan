import type { ReactNode } from "react";

import { CollectionShelf } from "@/components/crafts/CollectionShelf";
import { HubHeader, shelfAnchor } from "@/components/crafts/HubHeader";
import { ledSubFamilyShelves } from "@/components/crafts/shelfLead";
import { atlasPlate, familyCrafts, familyMaterial, familyName, isMonograph, shelfLead, subFamilyShelves, type AtlasShelf } from "@/lib/atlasCollection";
import { numberWord } from "@/lib/atlasIndex";
import type { CraftCatalogue, CraftCatalogueCategory } from "@/lib/craftCatalogueContract";

export function hubDek(catalogue: CraftCatalogue, category: CraftCatalogueCategory): string {
  const crafts = category.readerCount;
  const subs = subFamilyShelves(catalogue, category).length;
  const monographs = familyCrafts(catalogue, category).filter(isMonograph).length;
  const head = `${crafts.toLocaleString("en-IN")} ${crafts === 1 ? "craft" : "crafts"} in ${numberWord(subs)} ${subs === 1 ? "sub-family" : "sub-families"}.`;
  return monographs > 0 ? `${head} ${monographs} ${monographs === 1 ? "is a monograph" : "are monographs"}, read in full.` : head;
}

export function monographShelf(catalogue: CraftCatalogue, category: CraftCatalogueCategory): AtlasShelf | null {
  const crafts = familyCrafts(catalogue, category).filter(isMonograph);
  if (!crafts.length) return null;
  const lead = shelfLead(crafts);
  return {
    id: `${category.id}-monographs`,
    slug: category.slug,
    name: "Monographs",
    material: familyMaterial(category),
    count: crafts.length,
    subFamilies: [],
    lead: lead ? atlasPlate(category, lead) : null,
    plates: crafts.filter((craft) => craft !== lead).map((craft) => atlasPlate(category, craft)),
    more: [],
    big: crafts.length > 4,
    leadEnd: false
  };
}

export function CategoryHub({ catalogue, category, science }: { catalogue: CraftCatalogue; category: CraftCatalogueCategory; science: ReactNode }) {
  const monographs = monographShelf(catalogue, category);
  const shelves = ledSubFamilyShelves(subFamilyShelves(catalogue, category));
  return (
    <div className="grid gap-14 pb-section" data-testid="category-hub">
      <HubHeader name={familyName(category)} material={familyMaterial(category)} dek={hubDek(catalogue, category)} shelves={shelves} />
      {monographs ? <CollectionShelf shelf={monographs} level={2} priority /> : null}
      {science}
      <section aria-labelledby="hub-collection" className="border-t border-ink-1 pt-[22px]">
        <h2 id="hub-collection" className="mb-9 font-headline text-h2 text-ink-1">
          The collection
        </h2>
        <div className="grid gap-14">
          {shelves.map((shelf) => (
            <CollectionShelf key={shelf.id} id={shelfAnchor(shelf)} shelf={shelf} all={{ expand: shelf.more }} />
          ))}
        </div>
      </section>
    </div>
  );
}
