import type { ReactNode } from "react";

import { RenderedChemistryProvider } from "@/components/answer/RenderedChemistry";
import { DocumentLanguages } from "@/components/monograph/DocumentLanguages";
import { KitScript } from "@/components/monograph/KitScript";
import { KitShellTail } from "@/components/monograph/KitShellTail";
import { KitPreferences } from "@/components/monograph/ReaderSettings";
import { documentChemistry } from "@/lib/chemistryKeys";
import type { PageLanguages } from "@/lib/documentLanguages";
import { MONOGRAPH_KIT_CSS, type MonographDocument } from "@/lib/monographDocument";
import { renderedChemistry } from "@/lib/server/renderedChemistry";

export type MonographPageProps = { document: MonographDocument; masthead?: boolean; deferred?: boolean; languages?: PageLanguages | null };

type FrameProps = { document: MonographDocument; given: MonographDocument; dataDeferred: boolean; languages: PageLanguages | null; children: ReactNode };

export function MonographFrame({ document, given, dataDeferred, languages, children }: FrameProps) {
  return (
    <div className="kv-monograph ms-[calc(50%-50vw)] w-screen" lang={document.translation?.sourceLanguage ?? document.language} data-subject={`${document.subjectKind}:${document.subjectSlug}`} data-version={document.version}>
      <link rel="stylesheet" href={MONOGRAPH_KIT_CSS} precedence="default" />
      {languages ? <DocumentLanguages kind={document.subjectKind} slug={document.subjectSlug} current={document.language} languages={languages.languages} translation={document.translation} /> : null}
      <RenderedChemistryProvider rendered={renderedChemistry(documentChemistry(given))}>{children}</RenderedChemistryProvider>
      <KitShellTail document={document} dataDeferred={dataDeferred} />
      <KitPreferences />
      <KitScript />
    </div>
  );
}
