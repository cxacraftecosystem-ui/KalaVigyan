import { Fragment, type ReactNode } from "react";

import { CiteThis } from "@/components/craft/CiteThis";
import { AuthoredShell } from "@/components/monograph/AuthoredShell";
import { ComponentSlot, slotDrawing } from "@/components/monograph/ComponentSlot";
import { DocumentMasthead } from "@/components/monograph/DocumentMasthead";
import { KitScript } from "@/components/monograph/KitScript";
import { KitShellTail } from "@/components/monograph/KitShellTail";
import { MonographMasthead } from "@/components/monograph/MonographMasthead";
import { MonographPassage } from "@/components/monograph/MonographPassage";
import { MonographRail } from "@/components/monograph/MonographRail";
import { MonographSources } from "@/components/monograph/MonographSources";
import { KitPreferences } from "@/components/monograph/ReaderSettings";
import { SourceList } from "@/components/monograph/SourceList";
import { citeKey, versionedUrl, type Citable } from "@/lib/monographCite";
import { MONOGRAPH_KIT_CSS, type MonographDocument } from "@/lib/monographDocument";
import { componentKind, pagePlan, railChapters, type ChapterBlock, type ChapterPlan, type LabelMasthead, type MastheadPlan, type PagePlan } from "@/lib/monographRenderLayout";
import { componentPlace, type KitFrame } from "@/lib/monographScopes";

const CITED_SUBJECT = "craft";

function framed(frame: KitFrame, children: ReactNode): ReactNode {
  if (frame === "bare") return children;
  if (frame === "screen") return <div className="screen">{children}</div>;
  const inner = frame === "column" ? (
    <div className="spread">
      <div className="main">{children}</div>
    </div>
  ) : (
    children
  );
  return (
    <div className="screen">
      <div className="wrap kv-passage">{inner}</div>
    </div>
  );
}

function ComponentScope({ kind, children }: { kind: string | null; children: ReactNode }) {
  const place = componentPlace(kind);
  return (
    <div className={`bx bx-${place.scope}`} data-kind={kind ?? undefined}>
      {framed(place.frame, children)}
    </div>
  );
}

type BlockProps = { document: MonographDocument; chapter: ChapterPlan; block: ChapterBlock; labelled: boolean };

function BlockView({ document, chapter, block, labelled }: BlockProps) {
  if (block.kind === "passage") return <MonographPassage document={document} chapter={chapter} passage={block} />;
  if (block.kind === "component") {
    const slot = <ComponentSlot document={document} label={block.label} />;
    if (slotDrawing(document, block.label) !== "view") return slot;
    return <ComponentScope kind={componentKind(document, block.label)}>{slot}</ComponentScope>;
  }
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

type ChaptersProps = { document: MonographDocument; plan: PagePlan; masthead: boolean; rail: ReactNode };

function DocumentChapters({ document, plan, masthead, rail }: ChaptersProps) {
  const labelled = plan.label !== null;
  const cite = labelled ? documentCitation(document) : null;
  return (
    <div id="kv-main">
      {plan.chapters.map((chapter) => (
        <Fragment key={chapter.key}>
          <MonographChapter document={document} chapter={chapter} masthead={masthead && chapter.index === 0 ? plan.masthead : null} label={masthead && chapter.index === 0 ? plan.label : null} labelled={labelled} />
          {chapter.index === 0 ? rail : null}
        </Fragment>
      ))}
      {cite ? (
        <div className="kv-page kv-citethis-place" data-app="">
          <CiteThis cite={cite} />
        </div>
      ) : null}
    </div>
  );
}

export function railAfterMasthead(document: MonographDocument, plan: PagePlan, masthead: boolean): boolean {
  return document.shell === null && masthead && plan.label !== null && plan.chapters[0]?.index === 0;
}

export function MonographPage({ document, masthead = true }: { document: MonographDocument; masthead?: boolean }) {
  const plan = pagePlan(document);
  const rail = <MonographRail chapters={railChapters(plan)} />;
  const later = railAfterMasthead(document, plan, masthead);
  return (
    <div className="kv-monograph ms-[calc(50%-50vw)] w-screen" lang={document.language} data-subject={`${document.subjectKind}:${document.subjectSlug}`} data-version={document.version}>
      <link rel="stylesheet" href={MONOGRAPH_KIT_CSS} precedence="default" />
      {later ? null : rail}
      {document.shell !== null ? <AuthoredShell document={document} shell={document.shell} /> : <DocumentChapters document={document} plan={plan} masthead={masthead} rail={later ? rail : null} />}
      <KitShellTail document={document} />
      <KitPreferences />
      <KitScript />
    </div>
  );
}
