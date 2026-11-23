import { SourceRow } from "@/components/monograph/SourceList";
import type { MonographDocument } from "@/lib/monographDocument";
import { sentenceCounts } from "@/lib/monographRenderKit";
import { KIN_SOURCES_ID, sourceGroups, sourceSplit } from "@/lib/monographSources";

export const SOURCE_STATUS_ID = "kv-src-status";
export const KIN_SOURCES_TITLE = "For the kin crafts";
export const KIN_SOURCES_CLOSE = "Hide them";

function sourcesNoun(count: number): string {
  return count === 1 ? "source" : "sources";
}

export function sourcesDek(count: number): string {
  return `The monograph’s ${count} ${sourcesNoun(count)}, numbered as they first appear. Select one to light the sentences it supports.`;
}

export function kinSourcesDek(kin: number, own: number, chapter: number | null): string {
  const where = chapter === null ? "" : ` in chapter ${chapter}`;
  return `${kin} ${sourcesNoun(kin)} that support only the kin crafts’ sentences${where}. They are counted apart from the ${own} ${sourcesNoun(own)} of this monograph.`;
}

export function kinSourcesOpen(kin: number): string {
  return kin === 1 ? "Show the source" : `Show the ${kin} sources`;
}

type RowsProps = { document: MonographDocument; keys: readonly string[]; counts: ReadonlyMap<string, number> };

function Rows({ document, keys, counts }: RowsProps) {
  return (
    <ul>
      {keys.map((key) => (
        <SourceRow key={key} sourceKey={key} source={document.content.sources[key]} count={counts.get(key) ?? 0} />
      ))}
    </ul>
  );
}

function KinSources({ document, keys, counts, own, chapter }: RowsProps & { own: number; chapter: number | null }) {
  if (!keys.length) return null;
  return (
    <div className="kv-src-kin" id={KIN_SOURCES_ID}>
      <h3 className="kv-sub-h">{KIN_SOURCES_TITLE}</h3>
      <p className="kv-sub-d">{kinSourcesDek(keys.length, own, chapter)}</p>
      <details className="kv-more kv-src-more">
        <summary>
          <span className="kv-more-o">{kinSourcesOpen(keys.length)}</span>
          <span className="kv-more-c">{KIN_SOURCES_CLOSE}</span>
        </summary>
        <div className="sources kv-sources">
          <div className="src-group">
            <Rows document={document} keys={keys} counts={counts} />
          </div>
        </div>
      </details>
    </div>
  );
}

export function MonographSources({ document, kinChapter = null }: { document: MonographDocument; kinChapter?: number | null }) {
  const split = sourceSplit(document);
  const groups = sourceGroups(document, split.own);
  const counts = sentenceCounts(document);
  if (!split.own.length && !split.kin.length) return null;
  return (
    <div className="bx bx-rm">
      <div className="screen" data-aid="cite">
        <div className="wrap">
          <p className="src-dek">{sourcesDek(split.own.length)}</p>
          <div id={SOURCE_STATUS_ID} className="kv-src-status" role="status" />
          <div className="sources kv-sources">
            {groups.map((group) => (
              <div className="src-group" key={group.title}>
                <h3>{group.title}</h3>
                <Rows document={document} keys={group.keys} counts={counts} />
              </div>
            ))}
          </div>
          <KinSources document={document} keys={split.kin} counts={counts} own={split.own.length} chapter={kinChapter} />
        </div>
      </div>
    </div>
  );
}
