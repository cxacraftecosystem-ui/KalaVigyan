import type { MonographDocument, MonographSource } from "@/lib/monographDocument";
import { sentenceCounts } from "@/lib/monographRenderKit";
import { pageSources } from "@/lib/monographRenderLayout";
import { sourceReliabilityLabel } from "@/lib/citations";
import type { SourceReliability } from "@/lib/types";

const GRADES = new Set(["A", "B", "C", "D"]);

export function sourceByline(source: MonographSource): string | null {
  const parts = [source.publisher, source.year === null ? null : String(source.year)].filter((part): part is string => Boolean(part));
  return parts.length ? parts.join(", ") : null;
}

export function supportLine(count: number): string {
  return count === 1 ? "Supports 1 sentence here" : `Supports ${count} sentences here`;
}

export function SourceRow({ sourceKey, source, count }: { sourceKey: string; source: MonographSource; count: number }) {
  const byline = sourceByline(source);
  const grade = source.grade && GRADES.has(source.grade) ? (source.grade as SourceReliability) : null;
  return (
    <li className="kv-src-li">
      <button type="button" className="src" data-g={sourceKey} aria-pressed="false">
        <b>{source.number}</b>
        <span className="src-main">
          <span className="src-t">{source.fullTitle ?? source.title}</span>
          <small>
            {byline ? <span>{byline}</span> : null}
            {grade ? (
              <span className="relw">
                <span className={`rel ${grade}`} aria-hidden="true" />
                {sourceReliabilityLabel(grade)}
              </span>
            ) : null}
            <span>{supportLine(count)}</span>
          </small>
        </span>
      </button>
      {source.url ? (
        <a className="kv-src-link" href={source.url} rel="noopener" target="_blank">
          Open the source<span className="vh">: {source.title}</span>
        </a>
      ) : null}
    </li>
  );
}

export function SourceList({ document }: { document: MonographDocument }) {
  const counts = sentenceCounts(document);
  const keys = pageSources(document);
  if (!keys.length) return null;
  return (
    <div className="bx bx-rm">
      <section className="screen" data-aid="cite">
        <div className="wrap">
          <div className="sources kv-sources">
            <div className="src-group">
              <ul>
                {keys.map((key) => (
                  <SourceRow key={key} sourceKey={key} source={document.content.sources[key]} count={counts.get(key) ?? 0} />
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
