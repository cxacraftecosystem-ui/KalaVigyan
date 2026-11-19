import type { CompareRow } from "@/lib/explainerLearning";
import { DISCIPLINE_LABEL } from "@/lib/explainerView";

export type CompareLayout = { row: string; head: string; cell: string; cellName: string };
export type RowTitle = { title: string; facet: string | null };

const STACKED_ROW = "grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3 border-b border-rule py-3";
const STACKED_CELL = "grid min-w-0 content-start gap-1";
const HEAD = "gap-x-6 border-b border-rule pb-2";

const SIDE_BY_SIDE: Record<number, CompareLayout> = {
  2: {
    row: `${STACKED_ROW} sm:grid-cols-[minmax(0,8rem)_repeat(2,minmax(0,1fr))] sm:gap-x-6`,
    head: `max-sm:sr-only sm:grid ${HEAD} sm:grid-cols-[minmax(0,8rem)_repeat(2,minmax(0,1fr))]`,
    cell: STACKED_CELL,
    cellName: "sm:sr-only"
  },
  3: {
    row: `${STACKED_ROW} md:grid-cols-[minmax(0,8rem)_repeat(3,minmax(0,1fr))] md:gap-x-6`,
    head: `max-md:sr-only md:grid ${HEAD} md:grid-cols-[minmax(0,8rem)_repeat(3,minmax(0,1fr))]`,
    cell: STACKED_CELL,
    cellName: "md:sr-only"
  },
  4: {
    row: `${STACKED_ROW} lg:grid-cols-[minmax(0,8rem)_repeat(4,minmax(0,1fr))] lg:gap-x-6`,
    head: `max-lg:sr-only lg:grid ${HEAD} lg:grid-cols-[minmax(0,8rem)_repeat(4,minmax(0,1fr))]`,
    cell: STACKED_CELL,
    cellName: "lg:sr-only"
  }
};

export function compareLayout(craftCount: number): CompareLayout {
  const layout = SIDE_BY_SIDE[craftCount];
  if (!layout) throw new RangeError(`a comparison sets 2 to 4 crafts side by side, not ${craftCount}`);
  return layout;
}

export function rowTitle(row: CompareRow): RowTitle {
  const facet = DISCIPLINE_LABEL[row.facet];
  return row.term ? { title: row.term.label, facet } : { title: facet, facet: null };
}
