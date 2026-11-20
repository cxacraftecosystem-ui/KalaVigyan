"use client";

import { useMemo } from "react";

import { KitData, useRestShown } from "@/components/monograph/DeferredShell";
import { ChapterRun, PageCitation, shownPage } from "@/components/monograph/MonographChapters";
import { kitDataBlocks } from "@/lib/monographRenderKit";
import { restChapters, type DocumentRest } from "@/lib/monographRenderShell";

export function DeferredDocument({ part, jump }: { part: DocumentRest; jump: string | null }) {
  useRestShown(jump);
  const { document, plan } = useMemo(() => shownPage(part.document), [part.document]);
  return (
    <>
      <ChapterRun document={document} plan={plan} chapters={restChapters(plan.chapters)} masthead={false} rail={null} />
      <PageCitation document={document} plan={plan} />
      <KitData blocks={kitDataBlocks(document.content)} />
    </>
  );
}
