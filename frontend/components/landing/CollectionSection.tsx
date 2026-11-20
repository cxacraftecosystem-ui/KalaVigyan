import { DocumentWall } from "@/components/landing/DocumentWall";
import type { LandingCollection, LandingStat } from "@/components/landing/landingCollection";
import { TextLink } from "@/components/ui/TextLink";
import { numberWord } from "@/lib/atlasIndex";
import { cn } from "@/lib/utils";

export const COLLECTION_HEADING = "Read the collection";

function statValue(collection: LandingCollection, key: string): number {
  return collection.stats.find((stat) => stat.key === key)?.value ?? 0;
}

export function collectionDek(collection: LandingCollection): string {
  const families = statValue(collection, "families");
  const states = statValue(collection, "states");
  return `${collection.crafts.toLocaleString("en-IN")} crafts in ${numberWord(families)} ${families === 1 ? "family" : "families"}, from ${states} ${states === 1 ? "state or union territory" : "states and union territories"}. Every page is open to read: each craft has its plate and record, and the monographs are written out in full.`;
}

function Stat({ stat, last }: { stat: LandingStat; last: boolean }) {
  return (
    <div className={cn("flex flex-col-reverse justify-end gap-1 border-t border-ink-1 pt-2.5", last && "max-sm:col-span-2")} data-testid="landing-stat">
      <dt className="font-ui text-label text-ink-3">{stat.label}</dt>
      <dd className="m-0 font-headline text-stat text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{stat.value.toLocaleString("en-IN")}</dd>
    </div>
  );
}

export function CollectionSection({ collection }: { collection: LandingCollection }) {
  return (
    <section id="collection" className="scroll-mt-6 py-section" aria-labelledby="collection-h" data-testid="landing-collection">
      <div className="kv-shell-wrap">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-end lg:gap-16">
          <div className="min-w-0">
            <p className="kv-chapter-no">The collection</p>
            <h2 id="collection-h" className="m-0 font-headline text-h2 text-ink-1">
              {COLLECTION_HEADING}
            </h2>
            <p className="mt-4 max-w-measure font-reading text-lede text-ink-2">{collectionDek(collection)}</p>
            <p className="mt-4">
              <TextLink href="/crafts" standalone>
                {`Open the atlas of ${collection.crafts.toLocaleString("en-IN")} crafts`}
              </TextLink>
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 lg:grid-cols-5 lg:gap-x-5" data-testid="landing-stats">
            {collection.stats.map((stat, at) => (
              <Stat key={stat.key} stat={stat} last={at === collection.stats.length - 1 && collection.stats.length % 2 === 1} />
            ))}
          </dl>
        </div>
        <DocumentWall documents={collection.documents} />
      </div>
    </section>
  );
}
