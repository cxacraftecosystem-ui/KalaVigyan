import { CategoriesSection, CATEGORIES_ID } from "@/components/landing/CategoriesSection";
import { CollectionSection } from "@/components/landing/CollectionSection";
import type { FieldHoldings } from "@/components/landing/fieldHoldings";
import { FieldsSection } from "@/components/landing/FieldsSection";
import { HowToRead } from "@/components/landing/HowToRead";
import type { LandingCollection } from "@/components/landing/landingCollection";
import type { LandingContent } from "@/components/landing/landingContent";
import { LandingHero } from "@/components/landing/LandingHero";
import { PartnersFooter } from "@/components/landing/PartnersFooter";
import { CraftsMapSection } from "@/components/map/CraftsMapSection";
import { Appbar } from "@/components/nav/Appbar";
import { PublicNav } from "@/components/nav/PublicNav";
import { SkipLink } from "@/components/shell/ShellFrame";

export type LandingProps = { craftCount: number | null; content: LandingContent; collection: LandingCollection | null; fields: FieldHoldings | null };

export function Landing({ craftCount, content, collection, fields }: LandingProps) {
  return (
    <div className="kv-shell">
      <SkipLink />
      <Appbar brandHref="/" tone="photo" overlay>
        <PublicNav categoriesHref={collection ? `#${CATEGORIES_ID}` : undefined} />
      </Appbar>
      <main id="main-content" tabIndex={-1} className="flex-1">
        <LandingHero craftCount={craftCount} content={content} stats={collection?.stats ?? null} />
        {collection ? <CollectionSection collection={collection} /> : null}
        {collection ? <CategoriesSection families={collection.families} /> : null}
        <FieldsSection holdings={fields} />
        <HowToRead content={content} />
        <CraftsMapSection />
      </main>
      <PartnersFooter />
    </div>
  );
}
