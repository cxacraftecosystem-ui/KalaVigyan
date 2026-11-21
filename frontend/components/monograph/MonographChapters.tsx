import { Fragment, type ReactNode } from "react";

import { CiteThis } from "@/components/craft/CiteThis";
import { ComponentSlot } from "@/components/monograph/ComponentSlot";
import { DocumentMasthead } from "@/components/monograph/DocumentMasthead";
import { MonographMasthead } from "@/components/monograph/MonographMasthead";
import { MonographPassage } from "@/components/monograph/MonographPassage";
import { MonographSources } from "@/components/monograph/MonographSources";
import { SourceList } from "@/components/monograph/SourceList";
import { citeKey, versionedUrl, type Citable } from "@/lib/monographCite";
import type { MonographDocument } from "@/lib/monographDocument";
import type { ChapterBlock, ChapterPlan, LabelMasthead, MastheadPlan, PagePlan } from "@/lib/monographRenderLayout";

export { shownPage } from "@/lib/monographShownPage";

const CITED_SUBJECT = "craft";

type BlockProps = { document: MonographDocument; chapter: ChapterPlan; block: ChapterBlock; labelled: boolean };

function BlockView({ document, chapter, block, labelled }: BlockProps) {
  if (block.kind === "passage") return <MonographPassage document={document} chapter={chapter} passage={block} />;
  if (block.kind === "component") return <ComponentSlot document={document} label={block.label} />;
  return labelled ? <MonographSources document={document} /> : <SourceList document={document} />;
}

function blockKey(block: ChapterBlock, at: number): string {
  return block.kind === "component" ? block.label : `${block.kind}-${at}`;
}

type ChapterProps = { document: MonographDocument; chapter: ChapterPlan; masthead: MastheadPlan | null; label?: LabelMasthead | null; labelled?: boolean };

export function MonographChapter({ document, chapter, masthead, label = null, labelled = false }: ChapterProps) {
  return (
    <section className="kv-ch" id={chapter.key} data-ch={chapter.index} data-label={chapter.label} aria-label={chapter.label}>
      {label ? <DocumentMasthead document={document} label={label} /> : masthead ? <MonographMasthead document={document} masthead={masthead} /> : null}
      {chapter.blocks.map((block, at) => (
        <BlockView key={blockKey(block, at)} document={document} chapter={chapter} block={block} labelled={labelled} />
      ))}
    </section>
  );
}

export function documentCitation(document: MonographDocument): Citable | null {
  if (document.subjectKind !== CITED_SUBJECT) return null;
  return { kind: "monograph", title: document.title, version: document.version, url: versionedUrl(document.pageUrl, document.version), key: citeKey(document.subjectSlug, document.version) };
}

type RunProps = { document: MonographDocument; plan: PagePlan; chapters: readonly ChapterPlan[]; masthead: boolean; rail: ReactNode };

export function ChapterRun({ document, plan, chapters, masthead, rail }: RunProps) {
  const labelled = plan.label !== null;
  return (
    <>
      {chapters.map((chapter) => (
        <Fragment key={chapter.key}>
          <MonographChapter document={document} chapter={chapter} masthead={masthead && chapter.index === 0 ? plan.masthead : null} label={masthead && chapter.index === 0 ? plan.label : null} labelled={labelled} />
          {chapter.index === 0 ? rail : null}
        </Fragment>
      ))}
    </>
  );
}

export function PageCitation({ document, plan }: { document: MonographDocument; plan: PagePlan }) {
  const cite = plan.label !== null ? documentCitation(document) : null;
  if (!cite) return null;
  return (
    <div className="kv-page kv-citethis-place" data-app="">
      <CiteThis cite={cite} />
    </div>
  );
}
