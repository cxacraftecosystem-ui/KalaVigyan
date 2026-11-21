import type { ReactNode } from "react";

import { DeferredShellSlot } from "@/components/monograph/DeferredShellSlot";
import { KitDefs } from "@/components/monograph/KitDefs";
import { ChapterRun, PageCitation } from "@/components/monograph/MonographChapters";
import { MonographFrame, type MonographPageProps } from "@/components/monograph/MonographFrame";
import { MonographRail } from "@/components/monograph/MonographRail";
import type { MonographDocument } from "@/lib/monographDocument";
import { deferredRest, railAfterMasthead } from "@/lib/monographDeferred";
import { railChapters, type PagePlan } from "@/lib/monographRenderLayout";
import { leadChapters } from "@/lib/monographRenderShell";
import { shownPage } from "@/lib/monographShownPage";

type ChaptersProps = { document: MonographDocument; plan: PagePlan; masthead: boolean; rail: ReactNode; rest: string | null };

function DocumentChapters({ document, plan, masthead, rail, rest }: ChaptersProps) {
  return (
    <div id="kv-main">
      <ChapterRun document={document} plan={plan} chapters={rest === null ? plan.chapters : leadChapters(plan.chapters)} masthead={masthead} rail={rail} />
      {rest === null ? <PageCitation document={document} plan={plan} /> : <DeferredShellSlot src={rest} version={document.version} part="document" />}
    </div>
  );
}

export function MonographDocumentPage({ document: given, masthead = true, deferred = false }: MonographPageProps) {
  const { document, plan } = shownPage(given);
  const rail = <MonographRail chapters={railChapters(plan)} />;
  const later = railAfterMasthead(document, plan, masthead);
  const rest = deferredRest(given, plan, deferred);
  return (
    <MonographFrame document={document} given={given} dataDeferred={rest !== null}>
      {later ? null : rail}
      <DocumentChapters document={document} plan={plan} masthead={masthead} rail={later ? rail : null} rest={rest} />
      <KitDefs document={given} />
    </MonographFrame>
  );
}
