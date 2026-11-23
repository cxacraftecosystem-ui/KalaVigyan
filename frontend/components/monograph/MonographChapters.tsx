import { Fragment, type ReactNode } from "react";

import { CiteThis } from "@/components/craft/CiteThis";
import { FramedSubrail } from "@/components/monograph/ChapterSubrail";
import { ComponentSlot } from "@/components/monograph/ComponentSlot";
import { KitMasthead, PAGE_CITATION_ID } from "@/components/monograph/KitMasthead";
import { MonographContents } from "@/components/monograph/MonographContents";
import { MonographMasthead } from "@/components/monograph/MonographMasthead";
import { MonographPassage } from "@/components/monograph/MonographPassage";
import { MonographSources } from "@/components/monograph/MonographSources";
import { SourceList } from "@/components/monograph/SourceList";
import { documentCitation } from "@/lib/monographCite";
import type { MonographDocument } from "@/lib/monographDocument";
import { chapterNotes, chapterSections, type ChapterSection, type NoteLine } from "@/lib/monographNotes";
import { railChapters, type ChapterBlock, type ChapterPlan, type LabelMasthead, type MastheadPlan, type PagePlan } from "@/lib/monographRenderLayout";
import { KIN_KIND } from "@/lib/monographSources";

export { shownPage } from "@/lib/monographShownPage";

type ChapterParts = { notes: ReadonlyMap<string, NoteLine[]>; sections: readonly ChapterSection[]; kinChapter: number | null };
type BlockProps = { document: MonographDocument; chapter: ChapterPlan; block: ChapterBlock; labelled: boolean; parts: ChapterParts };

function BlockView({ document, chapter, block, labelled, parts }: BlockProps) {
  if (block.kind === "passage") return <MonographPassage document={document} chapter={chapter} passage={block} notes={parts.notes} sections={parts.sections} />;
  if (block.kind === "component") return <ComponentSlot document={document} label={block.label} />;
  return labelled ? <MonographSources document={document} kinChapter={parts.kinChapter} /> : <SourceList document={document} />;
}

function blockKey(block: ChapterBlock, at: number): string {
  return block.kind === "component" ? block.label : `${block.kind}-${at}`;
}

function Opening({ document, masthead, label, contents }: { document: MonographDocument; masthead: MastheadPlan | null; label: LabelMasthead | null; contents: readonly ChapterPlan[] }) {
  if (label) {
    return (
      <>
        <KitMasthead document={document} label={label} />
        <MonographContents chapters={contents} />
      </>
    );
  }
  return masthead ? <MonographMasthead document={document} masthead={masthead} /> : null;
}

type ChapterProps = { document: MonographDocument; chapter: ChapterPlan; masthead: MastheadPlan | null; label?: LabelMasthead | null; labelled?: boolean; contents?: readonly ChapterPlan[]; kinChapter?: number | null };

export function MonographChapter({ document, chapter, masthead, label = null, labelled = false, contents = [], kinChapter = null }: ChapterProps) {
  const parts: ChapterParts = { notes: chapterNotes(document, chapter), sections: chapterSections(document, chapter), kinChapter };
  const headed = chapter.blocks.some((block) => block.kind === "passage" && block.head && block.notes.length === 0);
  return (
    <section className="kv-ch" id={chapter.key} data-ch={chapter.index} data-label={chapter.label} aria-label={chapter.label}>
      <Opening document={document} masthead={masthead} label={label} contents={contents} />
      {headed ? null : <FramedSubrail sections={parts.sections} chapter={chapter.label} />}
      {chapter.blocks.map((block, at) => (
        <BlockView key={blockKey(block, at)} document={document} chapter={chapter} block={block} labelled={labelled} parts={parts} />
      ))}
    </section>
  );
}

export function kinChapterNumber(document: MonographDocument, plan: PagePlan): number | null {
  const kin = new Set(document.content.components.filter((component) => component.kind === KIN_KIND).map((component) => component.label));
  return plan.chapters.find((chapter) => chapter.blocks.some((block) => block.kind === "component" && kin.has(block.label)))?.number ?? null;
}

type RunProps = { document: MonographDocument; plan: PagePlan; chapters: readonly ChapterPlan[]; masthead: boolean; rail: ReactNode };

export function ChapterRun({ document, plan, chapters, masthead, rail }: RunProps) {
  const labelled = plan.label !== null;
  const kinChapter = kinChapterNumber(document, plan);
  const contents = railChapters(plan);
  return (
    <>
      {chapters.map((chapter) => {
        const opening = masthead && chapter.index === 0;
        return (
          <Fragment key={chapter.key}>
            <MonographChapter document={document} chapter={chapter} masthead={opening ? plan.masthead : null} label={opening ? plan.label : null} labelled={labelled} contents={contents} kinChapter={kinChapter} />
            {chapter.index === 0 ? rail : null}
          </Fragment>
        );
      })}
    </>
  );
}

export function PageCitation({ document, plan }: { document: MonographDocument; plan: PagePlan }) {
  const cite = plan.label !== null ? documentCitation(document) : null;
  if (!cite) return null;
  return (
    <div className="kv-page kv-citethis-place" id={PAGE_CITATION_ID} data-app="">
      <CiteThis cite={cite} />
    </div>
  );
}
