import { Fragment, type ReactNode } from "react";

import { UnitView } from "@/components/monograph/UnitView";
import type { MonographNode, MonographUnit } from "@/lib/monographDocument";
import type { MonographSources } from "@/lib/monographRender";
import { nodeElements } from "@/lib/monographRenderElements";
import { termRows, type TermGroup, type TermRow, type TermsPiece } from "@/lib/monographRenderLayout";

type Units = Readonly<Record<string, MonographUnit>>;
type GroupProps = { units: Units; sources: MonographSources; rows: readonly TermRow[] };

export function sentenceCased(nodes: readonly MonographNode[]): MonographNode[] {
  const [first, ...rest] = nodes;
  if (typeof first !== "string" || !/^[a-z]/.test(first)) return [...nodes];
  return [first.charAt(0).toUpperCase() + first.slice(1), ...rest];
}

function rowKey(row: TermRow, at: number): string {
  return row.term ?? row.values[0] ?? String(at);
}

function FactCells({ units, sources, rows }: GroupProps) {
  return (
    <dl className="glance">
      {rows.map((row, at) => (
        <div key={rowKey(row, at)}>
          {row.term ? <UnitView unit={units[row.term]} sources={sources} as="dt" /> : null}
          {row.values.map((ref) => (
            <UnitView key={ref} unit={units[ref]} sources={sources} as="dd" />
          ))}
        </div>
      ))}
    </dl>
  );
}

function joined(units: Units, sources: MonographSources, refs: readonly string[]): ReactNode {
  return refs.map((ref, at) => (
    <Fragment key={ref}>
      {at ? " " : null}
      {nodeElements(units[ref].nodes, sources)}
    </Fragment>
  ));
}

function RecordStrip({ units, sources, rows }: GroupProps) {
  return (
    <ol className="rec-list">
      {rows.map((row, at) => (
        <li key={rowKey(row, at)}>
          {row.term ? <UnitView unit={units[row.term]} sources={sources} as="p" className="rec-when" /> : null}
          <p className="rec-text">{joined(units, sources, row.values)}</p>
        </li>
      ))}
    </ol>
  );
}

function DifferBlocks({ units, sources, rows }: GroupProps) {
  return (
    <div className="kv-differs">
      {rows.map((row, at) => (
        <section className="kv-differ-item" key={rowKey(row, at)}>
          {row.term ? <h4 className="kv-differ-topic">{nodeElements(sentenceCased(units[row.term].nodes), sources)}</h4> : null}
          {row.values.map((ref) => (
            <UnitView key={ref} unit={units[ref]} sources={sources} as="p" />
          ))}
        </section>
      ))}
    </div>
  );
}

function EntryList({ units, sources, rows }: GroupProps) {
  return (
    <div className="kv-entries">
      {rows.map((row, at) => (
        <section className="kv-entry" key={rowKey(row, at)}>
          {row.term ? <UnitView unit={units[row.term]} sources={sources} as="h4" className="kv-entry-name" /> : null}
          {row.values.map((ref) => (
            <UnitView key={ref} unit={units[ref]} sources={sources} as="p" />
          ))}
        </section>
      ))}
    </div>
  );
}

const GROUP_VIEWS: Readonly<Record<TermGroup, (props: GroupProps) => ReactNode>> = {
  facts: FactCells,
  record: RecordStrip,
  differ: DifferBlocks,
  entries: EntryList
};

export function TermGroupView({ units, sources, piece }: { units: Units; sources: MonographSources; piece: TermsPiece }) {
  const View = GROUP_VIEWS[piece.group];
  return (
    <div className="kv-group" data-group={piece.group}>
      {piece.heading ? <UnitView unit={units[piece.heading]} sources={sources} as="h3" className="kv-group-h" /> : null}
      <View units={units} sources={sources} rows={termRows(units, piece.refs)} />
    </div>
  );
}
