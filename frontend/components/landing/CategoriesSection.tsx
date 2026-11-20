import Link from "next/link";

import { FamilySwatch } from "@/components/crafts/FamilySwatch";
import type { FamilyBlock } from "@/components/landing/landingCollection";
import { TextLink } from "@/components/ui/TextLink";
import { shelfSubLine } from "@/lib/atlasCollection";
import { numberWord } from "@/lib/atlasIndex";

export const CATEGORIES_ID = "categories";

export function categoriesHeading(count: number): string {
  const word = numberWord(count);
  return `${word.charAt(0).toUpperCase()}${word.slice(1)} ${count === 1 ? "family" : "families"} of craft`;
}

export function monographLine(count: number): string | null {
  if (count === 0) return null;
  return `${count} ${count === 1 ? "monograph" : "monographs"} read in full`;
}

function Family({ family }: { family: FamilyBlock }) {
  const monographs = monographLine(family.documents);
  return (
    <li className="grid content-start gap-3 border-t border-ink-1 pt-3.5" data-testid="landing-family">
      <h3 className="m-0">
        <Link href={family.href} className="group flex items-center gap-3">
          <FamilySwatch material={family.material} className="h-[42px] w-[34px]" />
          <span className="grid min-w-0 gap-0.5">
            <span className="font-reading text-h3 text-ink-1 group-hover:text-indigo group-hover:underline group-hover:decoration-1 group-hover:underline-offset-3">{family.name}</span>
            <span className="font-ui text-label text-ink-3 [font-variant-numeric:lining-nums_tabular-nums]">{[`${family.count} crafts`, monographs].filter(Boolean).join(" · ")}</span>
          </span>
        </Link>
      </h3>
      {family.subFamilies.length ? <p className="font-ui text-label text-ink-3">{shelfSubLine(family.subFamilies)}</p> : null}
      <p>
        <TextLink href={family.href} standalone>
          {`All ${family.count}`}
          <span className="sr-only">{` ${family.name} crafts`}</span>
        </TextLink>
      </p>
    </li>
  );
}

export function CategoriesSection({ families }: { families: readonly FamilyBlock[] }) {
  return (
    <section id={CATEGORIES_ID} className="scroll-mt-6 border-t border-rule py-section" aria-labelledby="categories-h" data-testid="landing-categories">
      <div className="kv-shell-wrap">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-end lg:gap-16">
          <div className="min-w-0">
            <p className="kv-chapter-no">Categories</p>
            <h2 id="categories-h" className="m-0 font-headline text-h2 text-ink-1">
              {categoriesHeading(families.length)}
            </h2>
          </div>
          <p className="max-w-measure font-reading text-body text-ink-2">Each family has its own page with the science its crafts share, its sub-families and every craft in it.</p>
        </div>
        <ul className="mt-10 grid gap-x-10 gap-y-8 md:grid-cols-2 lg:grid-cols-3">
          {families.map((family) => (
            <Family key={family.id} family={family} />
          ))}
        </ul>
      </div>
    </section>
  );
}
