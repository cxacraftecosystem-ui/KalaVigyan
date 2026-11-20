import { DocumentWall } from "@/components/landing/DocumentWall";
import type { LandingCollection } from "@/components/landing/landingCollection";
import { TextLink } from "@/components/ui/TextLink";

export const COLLECTION_HEADING = "Read the collection";

export const COLLECTION_DEK =
  "Every page is open to read. Each craft has its plate and its record, and each monograph is written out in full, from how the craft is made to its science, its place, its history and its people.";

export function CollectionSection({ collection }: { collection: LandingCollection }) {
  return (
    <section id="collection" className="scroll-mt-6 py-section" aria-labelledby="collection-h" data-testid="landing-collection">
      <div className="kv-shell-wrap">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-end lg:gap-16">
          <div className="min-w-0">
            <p className="kv-chapter-no">The collection</p>
            <h2 id="collection-h" className="m-0 font-headline text-h2 text-ink-1">
              {COLLECTION_HEADING}
            </h2>
          </div>
          <div className="min-w-0">
            <p className="max-w-measure font-reading text-lede text-ink-2">{COLLECTION_DEK}</p>
            <p className="mt-3">
              <TextLink href="/crafts" standalone>
                {`Open the atlas of ${collection.crafts.toLocaleString("en-IN")} crafts`}
              </TextLink>
            </p>
          </div>
        </div>
        <DocumentWall documents={collection.documents} />
      </div>
    </section>
  );
}
