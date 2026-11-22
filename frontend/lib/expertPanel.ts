import { EXPERT_SEAT_LABELS, type ExpertSeat, type ExpertViewBlock, type ExpertsDiffer } from "@/lib/explainerExperts";
import type { TypedBlock } from "@/lib/explainerView";
import { listText } from "@/lib/format";
import { joinedBy, onceSaid, sentenceKey } from "@/lib/sentenceGroups";

export type ExpertRun = { kind: "experts"; key: string; views: ExpertViewBlock[] };
export type SectionRun = { kind: "block"; block: TypedBlock } | ExpertRun;
export type DifferSide = { seat: ExpertSeat; label: string; view: ExpertsDiffer["views"][number] };
export type DifferCard = { key: string; sides: DifferSide[] };

export function sectionRuns(blocks: readonly TypedBlock[]): SectionRun[] {
  const runs: SectionRun[] = [];
  let panel: ExpertRun | null = null;
  for (const block of blocks) {
    if (block.kind !== "expert_view") runs.push({ kind: "block", block });
    else if (panel) panel.views.push(block);
    else {
      panel = { kind: "experts", key: block.id, views: [block] };
      runs.push(panel);
    }
  }
  return runs;
}

export function seatLabel(seat: ExpertSeat): string {
  return EXPERT_SEAT_LABELS[seat];
}

export function agreementText(view: Pick<ExpertViewBlock, "agreesWith">): string | null {
  return view.agreesWith.length > 0 ? `Agrees with ${listText(view.agreesWith.map(seatLabel))}` : null;
}

export function differSides(pair: ExpertsDiffer): [DifferSide, DifferSide] {
  const [first, second] = pair.seats;
  return [
    { seat: first, label: seatLabel(first), view: pair.views[0] },
    { seat: second, label: seatLabel(second), view: pair.views[1] }
  ];
}

export function differKey(pair: ExpertsDiffer): string {
  return pair.seats.join("+");
}

export function differCards(pairs: readonly ExpertsDiffer[]): DifferCard[] {
  return joinedBy(pairs, (pair) => pair.views.map(sentenceKey)).map((joined) => {
    const say = onceSaid();
    return { key: joined.map(differKey).join("|"), sides: joined.flatMap(differSides).filter((side) => say(side.view) !== null) };
  });
}
