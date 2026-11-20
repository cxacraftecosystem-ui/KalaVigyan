import type { ReactNode } from "react";

import { CollectionShelf } from "@/components/crafts/CollectionShelf";
import { ledSubFamilyShelves } from "@/components/crafts/shelfLead";
import { PlateGround } from "@/components/editorial/TypographicPlate";
import { atlasPlate, familyCrafts, familyMaterial, familyName, isMonograph, shelfLead, subFamilyShelves, type AtlasShelf } from "@/lib/atlasCollection";
import { numberWord } from "@/lib/atlasIndex";
import type { CraftCatalogue, CraftCatalogueCategory } from "@/lib/craftCatalogueContract";

export const HUB_KICKER = "Craft family";

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

function HubHeader({ catalogue, category }: { catalogue: CraftCatalogue; category: CraftCatalogueCategory }) {
  const material = familyMaterial(category);
  return (
    <header className="pt-6">
      <div className={`kv-plate g-${material} min-h-60 rounded-plate p-6 md:min-h-72 lg:p-10`} data-testid="hub-plate">
        <PlateGround material={material} />
        <div className="flex flex-1 flex-col items-start">
          <p className="kicker kv-knock m-0.5 text-inherit">{HUB_KICKER}</p>
          <h1 className="mt-auto pt-10 font-headline text-h1">
            <span className="kv-knock">{familyName(category)}</span>
          </h1>
        </div>
      </div>
      <p className="mt-5 max-w-[52ch] font-reading text-lede text-ink-2">{hubDek(catalogue, category)}</p>
    </header>
  );
}

export function CategoryHub({ catalogue, category, science }: { catalogue: CraftCatalogue; category: CraftCatalogueCategory; science: ReactNode }) {
  const monographs = monographShelf(catalogue, category);
  const shelves = ledSubFamilyShelves(subFamilyShelves(catalogue, category));
  return (
    <div className="grid gap-14 pb-section" data-testid="category-hub">
      <HubHeader catalogue={catalogue} category={category} />
      {monographs ? <CollectionShelf shelf={monographs} level={2} priority /> : null}
      {science}
      <section aria-labelledby="hub-collection" className="border-t border-ink-1 pt-[22px]">
        <h2 id="hub-collection" className="mb-9 font-headline text-h2 text-ink-1">
          The collection
        </h2>
        <div className="grid gap-14">
          {shelves.map((shelf) => (
            <CollectionShelf key={shelf.id} shelf={shelf} all={{ expand: shelf.more }} />
          ))}
        </div>
      </section>
    </div>
  );
}
