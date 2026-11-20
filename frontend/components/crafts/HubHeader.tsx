import { PlateGround, type PlateMaterial } from "@/components/editorial/TypographicPlate";
import type { AtlasShelf } from "@/lib/atlasCollection";

export const HUB_KICKER = "Craft family";
export const SUB_FAMILIES_LABEL = "Sub-families";

export function shelfAnchor(shelf: Pick<AtlasShelf, "id">): string {
  return `shelf-${shelf.id.replace(/[^A-Za-z0-9_-]/g, "")}`;
}

function SubFamilyIndex({ shelves }: { shelves: readonly AtlasShelf[] }) {
  if (shelves.length < 2) return null;
  return (
    <nav aria-label={SUB_FAMILIES_LABEL} className="min-w-0" data-testid="hub-index">
      <p className="kicker border-b border-rule pb-2">{SUB_FAMILIES_LABEL}</p>
      <ol>
        {shelves.map((shelf) => (
          <li key={shelf.id}>
            <a href={`#${shelfAnchor(shelf)}`} className="group flex items-baseline gap-3 border-b border-rule py-[9px]">
              <span className="font-reading text-body-sm font-medium text-ink-1 group-hover:text-indigo group-hover:underline group-hover:underline-offset-3">{shelf.name}</span>
              <b className="ms-auto font-ui text-ui font-medium text-ink-2 [font-variant-numeric:tabular-nums]">{shelf.count}</b>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function HubHeader({ name, material, dek, shelves }: { name: string; material: PlateMaterial; dek: string; shelves: readonly AtlasShelf[] }) {
  const indexed = shelves.length >= 2;
  return (
    <header className={indexed ? "grid gap-6 pt-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-12" : "pt-6"}>
      <div className={`kv-plate g-${material} min-h-60 rounded-plate p-6 md:min-h-72 lg:p-10`} data-testid="hub-plate">
        <PlateGround material={material} />
        <div className="flex flex-1 flex-col items-start">
          <p className="kicker kv-knock m-0.5 text-inherit">{HUB_KICKER}</p>
          <h1 className="mt-auto pt-10 font-headline text-h1">
            <span className="kv-knock">{name}</span>
          </h1>
        </div>
      </div>
      <div className={indexed ? "grid content-end gap-6" : undefined}>
        <p className={indexed ? "max-w-[52ch] font-reading text-lede text-ink-2" : "mt-5 max-w-[52ch] font-reading text-lede text-ink-2"}>{dek}</p>
        <SubFamilyIndex shelves={shelves} />
      </div>
    </header>
  );
}
