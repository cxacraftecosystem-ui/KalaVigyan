import type { ReactNode } from "react";

import { RenderedChemistryProvider } from "@/components/answer/RenderedChemistry";
import { KitScript } from "@/components/monograph/KitScript";
import { KitShellTail } from "@/components/monograph/KitShellTail";
import { KitPreferences } from "@/components/monograph/ReaderSettings";
import { documentChemistry } from "@/lib/chemistryKeys";
import { MONOGRAPH_KIT_CSS, type MonographDocument } from "@/lib/monographDocument";
import { renderedChemistry } from "@/lib/server/renderedChemistry";

export type MonographPageProps = { document: MonographDocument; masthead?: boolean; deferred?: boolean };

type FrameProps = { document: MonographDocument; given: MonographDocument; dataDeferred: boolean; children: ReactNode };

export function MonographFrame({ document, given, dataDeferred, children }: FrameProps) {
  return (
    <div className="kv-monograph ms-[calc(50%-50vw)] w-screen" lang={document.language} data-subject={`${document.subjectKind}:${document.subjectSlug}`} data-version={document.version}>
      <link rel="stylesheet" href={MONOGRAPH_KIT_CSS} precedence="default" />
      <RenderedChemistryProvider rendered={renderedChemistry(documentChemistry(given))}>{children}</RenderedChemistryProvider>
      <KitShellTail document={document} dataDeferred={dataDeferred} />
      <KitPreferences />
      <KitScript />
    </div>
  );
}
