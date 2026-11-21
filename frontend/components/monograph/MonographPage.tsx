import type { ReactNode } from "react";

import { AuthoredShell } from "@/components/monograph/AuthoredShell";
import { DeferredShellSlot } from "@/components/monograph/DeferredShellSlot";
import { KitScript } from "@/components/monograph/KitScript";
import { KitShellTail } from "@/components/monograph/KitShellTail";
import { ChapterRun, PageCitation, shownPage } from "@/components/monograph/MonographChapters";
import { MonographRail } from "@/components/monograph/MonographRail";
import { KitPreferences } from "@/components/monograph/ReaderSettings";
import { MONOGRAPH_KIT_CSS, type MonographDocument } from "@/lib/monographDocument";
import { railChapters, type PagePlan } from "@/lib/monographRenderLayout";
import { documentDigest, leadChapters, shellRestPath } from "@/lib/monographRenderShell";

const CITED_SUBJECT = "craft";

type ChaptersProps = { document: MonographDocument; plan: PagePlan; masthead: boolean; rail: ReactNode; rest: string | null };

function DocumentChapters({ document, plan, masthead, rail, rest }: ChaptersProps) {
  return (
    <div id="kv-main">
      <ChapterRun document={document} plan={plan} chapters={rest === null ? plan.chapters : leadChapters(plan.chapters)} masthead={masthead} rail={rail} />
      {rest === null ? <PageCitation document={document} plan={plan} /> : <DeferredShellSlot src={rest} version={document.version} part="document" />}
    </div>
  );
}

export function railAfterMasthead(document: MonographDocument, plan: PagePlan, masthead: boolean): boolean {
  return document.shell === null && masthead && plan.label !== null && plan.chapters[0]?.index === 0;
}

export function deferredRest(document: MonographDocument, plan: PagePlan, deferred: boolean): string | null {
  if (!deferred) return null;
  if (document.shell !== null) return document.subjectKind === CITED_SUBJECT ? shellRestPath(document.subjectSlug, document.version) : null;
  if (plan.chapters.length <= leadChapters(plan.chapters).length) return null;
  return shellRestPath(document.subjectSlug, document.version, document.subjectKind, documentDigest(document));
}

type MonographPageProps = { document: MonographDocument; masthead?: boolean; deferred?: boolean };

export function MonographPage({ document: given, masthead = true, deferred = false }: MonographPageProps) {
  const { document, plan } = shownPage(given);
  const rail = <MonographRail chapters={railChapters(plan)} />;
  const later = railAfterMasthead(document, plan, masthead);
  const rest = deferredRest(given, plan, deferred);
  return (
    <div className="kv-monograph ms-[calc(50%-50vw)] w-screen" lang={document.language} data-subject={`${document.subjectKind}:${document.subjectSlug}`} data-version={document.version}>
      <link rel="stylesheet" href={MONOGRAPH_KIT_CSS} precedence="default" />
      {later ? null : rail}
      {document.shell !== null ? <AuthoredShell document={document} shell={document.shell} rest={rest} /> : <DocumentChapters document={document} plan={plan} masthead={masthead} rail={later ? rail : null} rest={rest} />}
      <KitShellTail document={document} dataDeferred={rest !== null} />
      <KitPreferences />
      <KitScript />
    </div>
  );
}
