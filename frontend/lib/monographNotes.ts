import type { MonographDocument, MonographUnit } from "@/lib/monographDocument";
import { citedSourceKeys, nodesText } from "@/lib/monographRender";
import { passageSegments, type ChapterPlan, type PassagePiece } from "@/lib/monographRenderLayout";

export type NoteLine = { key: string; number: number; title: string; year: number | null };
export type ChapterSection = { id: string; ref: string; title: string };

type Units = Readonly<Record<string, MonographUnit>>;

const HEADING_TAGS: ReadonlySet<string> = new Set(["h2", "h3", "h4"]);
const SECTION_TAG = "h3";
const SUBRAIL_MIN = 2;

export function pieceRefs(piece: PassagePiece): string[] {
  return piece.kind === "unit" ? [piece.ref] : piece.refs;
}

function closesRun(piece: PassagePiece, units: Units): boolean {
  if (piece.kind === "paragraph" || piece.kind === "list") return true;
  if (piece.kind !== "unit") return false;
  return (piece.role === "text" || piece.role === "lede") && !HEADING_TAGS.has(units[piece.ref]?.tag ?? "");
}

function opensSection(piece: PassagePiece, units: Units): boolean {
  return piece.kind === "unit" && units[piece.ref]?.tag === SECTION_TAG;
}

export function spreadRuns(pieces: readonly PassagePiece[], units: Units): PassagePiece[][] {
  const runs: PassagePiece[][] = [];
  let open: PassagePiece[] = [];
  for (const piece of pieces) {
    if (open.length && opensSection(piece, units)) {
      runs.push(open);
      open = [];
    }
    open.push(piece);
    if (!closesRun(piece, units)) continue;
    runs.push(open);
    open = [];
  }
  return open.length ? [...runs, open] : runs;
}

export function runKey(run: readonly PassagePiece[]): string {
  return run.flatMap(pieceRefs)[0] ?? "";
}

export function noteLines(document: MonographDocument, refs: readonly string[], seen: Set<string> = new Set()): NoteLine[] {
  const { units, sources } = document.content;
  const keys = [...new Set(refs.flatMap((ref) => citedSourceKeys(units[ref]?.nodes ?? [])))].filter((key) => Object.hasOwn(sources, key) && !seen.has(key));
  keys.forEach((key) => seen.add(key));
  return keys.map((key) => ({ key, number: sources[key].number, title: sources[key].title, year: sources[key].year })).sort((a, b) => a.number - b.number);
}

export function chapterNotes(document: MonographDocument, chapter: ChapterPlan): Map<string, NoteLine[]> {
  const units = document.content.units;
  const seen = new Set<string>();
  const notes = new Map<string, NoteLine[]>();
  for (const block of chapter.blocks) {
    if (block.kind !== "passage" || block.notes.length) continue;
    for (const segment of passageSegments(block.pieces)) {
      if (segment.kind !== "column") continue;
      for (const run of spreadRuns(segment.pieces, units)) notes.set(runKey(run), noteLines(document, run.flatMap(pieceRefs), seen));
    }
  }
  return notes;
}

export function sectionId(chapter: string, ref: string): string {
  return `${chapter}-${ref.replace(/[^A-Za-z0-9_-]/g, "-")}`;
}

function sectionHeads(pieces: readonly PassagePiece[], units: Units): string[] {
  return pieces.flatMap((piece) => {
    if (piece.kind === "terms") return piece.heading ? [piece.heading] : [];
    return piece.kind === "unit" && units[piece.ref]?.tag === SECTION_TAG ? [piece.ref] : [];
  });
}

export function chapterSections(document: MonographDocument, chapter: ChapterPlan): ChapterSection[] {
  const units = document.content.units;
  const refs = chapter.blocks.flatMap((block) => (block.kind === "passage" ? sectionHeads(block.pieces, units) : []));
  const sections = refs.map((ref) => ({ id: sectionId(chapter.key, ref), ref, title: nodesText(units[ref].nodes).trim() })).filter((section) => section.title.length > 0);
  return sections.length >= SUBRAIL_MIN ? sections : [];
}
