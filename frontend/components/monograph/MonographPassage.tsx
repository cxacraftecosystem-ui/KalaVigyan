import { Fragment, type ReactNode } from "react";

import { ChapterSubrail } from "@/components/monograph/ChapterSubrail";
import { CitedList } from "@/components/monograph/CitedList";
import { NoteList } from "@/components/monograph/NoteList";
import { TermGroupView } from "@/components/monograph/TermGroups";
import { unitNodes, UnitView } from "@/components/monograph/UnitView";
import type { MonographDocument, MonographUnit } from "@/lib/monographDocument";
import { runKey, sectionId, spreadRuns, type ChapterSection, type NoteLine } from "@/lib/monographNotes";
import { passageSegments, type ChapterPlan, type Passage, type PassagePiece, type PassageSegment, type UnitRole } from "@/lib/monographRenderLayout";

import "./documentPage.css";

type Drawn = { as: string; className?: string };

const ROLE_DRAWING: Readonly<Record<Exclude<UnitRole, "text">, Drawn>> = {
  numeral: { as: "p", className: "chapter-no in-main" },
  kicker: { as: "p", className: "kicker sec-kicker" },
  title: { as: "h2", className: "t-h2" },
  lede: { as: "p", className: "t-lede" },
  label: { as: "p", className: "kicker" }
};

const TEXT_DRAWING: Readonly<Record<string, Drawn>> = {
  h3: { as: "h3", className: "font-reading text-h3 mt-8" },
  h4: { as: "h4", className: "font-ui text-h4 mt-6" },
  blockquote: { as: "blockquote", className: "font-reading text-quote italic" }
};

const SECTION_TAG = "h3";

export const MARGIN_LABEL = "Sources in this passage";

function drawing(unit: MonographUnit, role: UnitRole): Drawn {
  if (role !== "text") return ROLE_DRAWING[role];
  return TEXT_DRAWING[unit.tag] ?? { as: "p", className: "t-body" };
}

function pieceId(chapter: ChapterPlan, piece: Extract<PassagePiece, { kind: "unit" }>, unit: MonographUnit, titled: boolean): string | undefined {
  if (piece.role === "title" && titled) return `${chapter.key}-h`;
  return unit.tag === SECTION_TAG ? sectionId(chapter.key, piece.ref) : undefined;
}

type PieceProps = { document: MonographDocument; chapter: ChapterPlan; piece: PassagePiece; titled: boolean };

function Piece({ document, chapter, piece, titled }: PieceProps) {
  const { units, sources } = document.content;
  if (piece.kind === "list") return <CitedList units={units} sources={sources} refs={piece.refs} />;
  if (piece.kind === "terms") return <TermGroupView units={units} sources={sources} piece={piece} chapter={chapter.key} />;
  if (piece.kind === "paragraph") {
    return (
      <p className={piece.lede ? "t-lede" : "t-body"}>
        {piece.refs.map((ref, at) => (
          <Fragment key={ref}>
            {at ? " " : null}
            {unitNodes(units[ref], sources)}
          </Fragment>
        ))}
      </p>
    );
  }
  const unit = units[piece.ref];
  const drawn = drawing(unit, piece.role);
  return <UnitView unit={unit} sources={sources} as={drawn.as} className={drawn.className} id={pieceId(chapter, piece, unit, titled)} />;
}

function firstTitle(passage: Passage): string | null {
  const found = passage.pieces.find((piece) => piece.kind === "unit" && piece.role === "title");
  return found && found.kind === "unit" ? found.ref : null;
}

type PassageProps = { document: MonographDocument; chapter: ChapterPlan; passage: Passage; notes: ReadonlyMap<string, NoteLine[]>; sections: readonly ChapterSection[] };

function FixedNotes({ document, passage }: { document: MonographDocument; passage: Passage }) {
  const { units, sources } = document.content;
  if (!passage.notes.length) return null;
  return (
    <aside className="margin note" aria-label={MARGIN_LABEL}>
      <ul>
        {passage.notes.map((note) => (
          <li key={note.ref} data-g={note.source}>
            {unitNodes(units[note.ref], sources)}
          </li>
        ))}
      </ul>
    </aside>
  );
}

export function needsNumeral(passage: Passage, number: number | null): boolean {
  return passage.head && number !== null && !passage.pieces.some((piece) => piece.kind === "unit" && piece.role === "numeral");
}

function pieceKey(piece: PassagePiece, at: number): string {
  if (piece.kind === "unit") return piece.ref;
  return `${piece.kind}-${piece.refs[0] ?? at}`;
}

type SpreadProps = Omit<PassageProps, "notes" | "sections"> & { pieces: readonly PassagePiece[]; head: boolean; run: boolean };

function Spread({ document, chapter, passage, pieces, head, run, children }: SpreadProps & { children: ReactNode }) {
  const title = passage.head ? firstTitle(passage) : null;
  const classes = ["spread", head ? "railed sec-head" : null, run ? "kv-run" : null].filter(Boolean).join(" ");
  return (
    <div className={classes}>
      {head && chapter.number !== null ? (
        <div className="rail">
          <span className="numeral">{chapter.number}</span>
        </div>
      ) : null}
      <div className="main prose">
        {head && needsNumeral(passage, chapter.number) ? <p className="chapter-no in-main">{chapter.number}</p> : null}
        {pieces.map((piece, at) => (
          <Piece key={pieceKey(piece, at)} document={document} chapter={chapter} piece={piece} titled={piece.kind === "unit" && piece.ref === title} />
        ))}
      </div>
      {children}
    </div>
  );
}

function shownSegments(passage: Passage): PassageSegment[] {
  const segments = passageSegments(passage.pieces);
  if (!passage.notes.length || segments.some((segment) => segment.kind === "column")) return segments;
  return [{ kind: "column", pieces: [] }, ...segments];
}

function Column({ document, chapter, passage, notes, sections, pieces, first }: PassageProps & { pieces: readonly PassagePiece[]; first: boolean }) {
  if (passage.notes.length) {
    return (
      <Spread document={document} chapter={chapter} passage={passage} pieces={pieces} head={passage.head && first} run={false}>
        {first ? <FixedNotes document={document} passage={passage} /> : null}
      </Spread>
    );
  }
  const runs = spreadRuns(pieces, document.content.units);
  return (
    <>
      {runs.map((run, at) => {
        const head = passage.head && first && at === 0;
        return (
          <Fragment key={runKey(run)}>
            <Spread document={document} chapter={chapter} passage={passage} pieces={run} head={head} run>
              <NoteList notes={notes.get(runKey(run)) ?? []} label={MARGIN_LABEL} />
            </Spread>
            {head ? <ChapterSubrail sections={sections} chapter={chapter.label} /> : null}
          </Fragment>
        );
      })}
    </>
  );
}

function Segments({ document, chapter, passage, notes, sections }: PassageProps) {
  const segments = shownSegments(passage);
  const firstColumn = segments.findIndex((segment) => segment.kind === "column");
  const { units, sources } = document.content;
  return (
    <>
      {segments.map((segment, at) =>
        segment.kind === "group" ? (
          <TermGroupView key={pieceKey(segment.piece, at)} units={units} sources={sources} piece={segment.piece} chapter={chapter.key} />
        ) : (
          <Column key={`column-${at}`} document={document} chapter={chapter} passage={passage} notes={notes} sections={sections} pieces={segment.pieces} first={at === firstColumn} />
        )
      )}
    </>
  );
}

export function MonographPassage({ document, chapter, passage, notes, sections }: PassageProps) {
  const title = passage.head ? firstTitle(passage) : null;
  const spread = <Segments document={document} chapter={chapter} passage={passage} notes={notes} sections={sections} />;
  return (
    <div className="bx bx-pt">
      <div className="screen">
        {passage.head ? (
          <section className="sec wrap" aria-labelledby={title ? `${chapter.key}-h` : undefined}>
            {spread}
          </section>
        ) : (
          <div className="wrap kv-passage">{spread}</div>
        )}
      </div>
    </div>
  );
}
