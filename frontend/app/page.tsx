import { curatedClaimId } from "@/components/landing/curatedClaim";
import { serverFieldHoldings } from "@/components/landing/fieldCoverageServer";
import { Landing } from "@/components/landing/Landing";
import { landingCollection } from "@/components/landing/landingCollection";
import { LANDING_CRAFT_SLUG, landingContent } from "@/components/landing/landingContent";
import { publicSummary } from "@/lib/server/publicSummary";
import { serverCraftCatalogue, serverCraftPage } from "@/lib/server/readingPages";

export default async function LandingPage() {
  const [summary, page, catalogue] = await Promise.all([publicSummary(), serverCraftPage(LANDING_CRAFT_SLUG), serverCraftCatalogue()]);
  const fields = await serverFieldHoldings(catalogue);
  const content = landingContent(page, (key) => curatedClaimId(LANDING_CRAFT_SLUG, key));
  const craftCount = summary?.counts.crafts ?? catalogue?.summary.crafts ?? null;
  return <Landing craftCount={craftCount} content={content} collection={landingCollection(catalogue)} fields={fields} />;
}
