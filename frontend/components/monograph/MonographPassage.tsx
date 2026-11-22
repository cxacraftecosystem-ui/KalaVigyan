import { Fragment } from "react";

import { CitedList } from "@/components/monograph/CitedList";
import { TermGroupView } from "@/components/monograph/TermGroups";
import { unitNodes, UnitView } from "@/components/monograph/UnitView";
import type { MonographDocument, MonographUnit } from "@/lib/monographDocument";
import { passageSegments, type ChapterPlan, type Passage, type PassagePiece, type PassageSegment, type UnitRole } from "@/lib/monographRenderLayout";

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

export const MARGIN_LABEL = "Sources in this passage";

function drawing(unit: MonographUnit, role: UnitRole): Drawn {
  if (role !== "text") return ROLE_DRAWING[role];
  return TEXT_DRAWING[unit.tag] ?? { as: "p", className: "t-body" };
}

type PieceProps = { document: MonographDocument; chapter: ChapterPlan; piece: PassagePiece; titled: boolean };

function Piece({ document, chapter, piece, titled }: PieceProps) {
  const { units, sources } = document.content;
  if (piece.kind === "list") return <CitedList units={units} sources={sources} refs={piece.refs} />;
  if (piece.kind === "terms") return <TermGroupView units={units} sources={sources} piece={piece} />;
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
  const id = piece.role === "title" && titled ? `${chapter.key}-h` : undefined;
  return <UnitView unit={unit} sources={sources} as={drawn.as} className={drawn.className} id={id} />;
}

function firstTitle(passage: Passage): string | null {
  const found = passage.pieces.find((piece) => piece.kind === "unit" && piece.role === "title");
  return found && found.kind === "unit" ? found.ref : null;
}

type PassageProps = { document: MonographDocument; chapter: ChapterPlan; passage: Passage };

function MarginNotes({ document, passage }: Omit<PassageProps, "chapter">) {
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

type SpreadProps = PassageProps & { pieces: readonly PassagePiece[]; first: boolean };

function Spread({ document, chapter, passage, pieces, first }: SpreadProps) {
  const title = passage.head ? firstTitle(passage) : null;
  const head = passage.head && first;
  return (
    <div className={head ? "spread railed sec-head" : "spread"}>
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
      {first ? <MarginNotes document={document} passage={passage} /> : null}
    </div>
  );
}

function shownSegments(passage: Passage): PassageSegment[] {
  const segments = passageSegments(passage.pieces);
  if (!passage.notes.length || segments.some((segment) => segment.kind === "column")) return segments;
  return [{ kind: "column", pieces: [] }, ...segments];
}

function Segments({ document, chapter, passage }: PassageProps) {
  const segments = shownSegments(passage);
  const firstColumn = segments.findIndex((segment) => segment.kind === "column");
  const { units, sources } = document.content;
  return (
    <>
      {segments.map((segment, at) =>
        segment.kind === "group" ? (
          <TermGroupView key={pieceKey(segment.piece, at)} units={units} sources={sources} piece={segment.piece} />
        ) : (
          <Spread key={`column-${at}`} document={document} chapter={chapter} passage={passage} pieces={segment.pieces} first={at === firstColumn} />
        )
      )}
    </>
  );
}

export function MonographPassage({ document, chapter, passage }: PassageProps) {
  const title = passage.head ? firstTitle(passage) : null;
  const spread = <Segments document={document} chapter={chapter} passage={passage} />;
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
