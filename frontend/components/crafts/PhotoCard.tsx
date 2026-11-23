import Link from "next/link";

import { PlatePicture } from "@/components/editorial/Plate";
import { PlateTags } from "@/components/crafts/CollectionPlate";
import type { AtlasPlate } from "@/lib/atlasCollection";
import type { CatalogueHero } from "@/lib/craftCatalogueContract";
import { photoCredit } from "@/lib/editorialText";
import { pictureSources } from "@/lib/pictureSources";
import { cn } from "@/lib/utils";

const COMMONS_SITE = /commons\.wikimedia\.org|wikimedia commons/i;

export function heroCredit(hero: CatalogueHero): string {
  if (hero.licence && COMMONS_SITE.test(hero.site)) return photoCredit(hero.author, hero.licence);
  return [`Photo: ${hero.author}`, hero.licence, hero.site].filter(Boolean).join(", ");
}

export function PhotoCard({ plate, hero, big, priority = false, className }: { plate: AtlasPlate; hero: CatalogueHero; big: boolean; priority?: boolean; className?: string }) {
  return (
    <Link href={plate.href} className={cn("group flex min-w-0 flex-col overflow-hidden rounded-plate border border-rule bg-raised text-ink-1", className)} data-testid="photo-card">
      <PlatePicture
        alt={hero.alt}
        sources={pictureSources(hero.url, "lead", hero.width ?? undefined)}
        priority={priority}
        className={cn("aspect-[4/3] rounded-none", big ? "md:aspect-auto md:min-h-0 md:flex-1 md:[&_img]:absolute md:[&_img]:inset-0" : "md:aspect-[2/1]")}
      />
      <span className="grid gap-[3px] px-3 pt-2.5 pb-[11px]">
        {plate.kicker ? <span className="kicker">{plate.kicker}</span> : null}
        <span className="font-reading text-h3 group-hover:text-indigo group-hover:underline group-hover:decoration-1 group-hover:underline-offset-3">{plate.craft.displayName}</span>
        <span className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 font-ui text-caption text-ink-3">
          <span>{plate.state}</span>
          <PlateTags plate={plate} />
        </span>
        <span className="font-ui text-caption text-ink-3">{heroCredit(hero)}</span>
      </span>
    </Link>
  );
}
