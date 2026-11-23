import { ComponentSlot } from "@/components/monograph/ComponentSlot";
import { UnitView } from "@/components/monograph/UnitView";
import type { MonographDocument } from "@/lib/monographDocument";
import { gradeTally, type GradeTally } from "@/lib/monographRenderKit";
import type { MastheadPlan } from "@/lib/monographRenderLayout";
import { KIN_SOURCES_ID, sourceSplit } from "@/lib/monographSources";

export const LISTEN_KIND = "audio_player";
export const CITE_KIND = "citation_tool";
export const CITE_LABEL = "Cite this monograph";
const NARROW_SPACE = " ";

export function provenanceLine(tally: GradeTally): { drawn: string; reliability: string } {
  const noun = tally.total === 1 ? "source" : "sources";
  const graded = tally.grades.map((found) => `${found.count} graded ${found.grade}`).join(", ");
  return { drawn: `Drawn from ${tally.total} ${noun}`, reliability: `Reliability of the ${tally.total} ${noun}: ${graded}` };
}

export function kinLine(count: number): string {
  return `${count} more for the kin crafts`;
}

export function OpenProvenance({ tally, kin }: { tally: GradeTally; kin: number }) {
  if (tally.total === 0) return null;
  const line = provenanceLine(tally);
  return (
    <p className="kv-open-prov">
      <span className="kv-prov-n">{line.drawn}</span>
      {tally.grades.length ? (
        <span className="rel-strip" role="img" aria-label={line.reliability}>
          {tally.grades.map((found) => (
            <span className="rs-g" key={found.grade}>
              <span className={`rel ${found.grade}`} aria-hidden="true" />
              {`${found.grade}${NARROW_SPACE}${found.count}`}
            </span>
          ))}
        </span>
      ) : null}
      {kin ? (
        <a className="kv-prov-k" href={`#${KIN_SOURCES_ID}`}>
          {kinLine(kin)}
        </a>
      ) : null}
    </p>
  );
}

export function citeAnchor(document: MonographDocument, fallback: string | null): string | null {
  const tool = document.content.components.find((component) => component.kind === CITE_KIND && component.anchor.startsWith("#"));
  return tool?.anchor ?? fallback;
}

export function MastheadTools({ document, cite }: { document: MonographDocument; cite: string | null }) {
  const listen = document.content.components.some((component) => component.kind === LISTEN_KIND);
  if (!listen && !cite) return null;
  return (
    <div className="kv-open-act">
      {listen ? (
        <button className="btn" type="button" data-listen-open="" aria-controls="kv-player">
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M4.5 2.8 L13 8 L4.5 13.2 Z" fill="currentColor" />
          </svg>
          <span>Listen</span>
        </button>
      ) : null}
      {cite ? (
        <a className="btn" href={cite}>
          {CITE_LABEL}
        </a>
      ) : null}
    </div>
  );
}

export function MonographMasthead({ document, masthead }: { document: MonographDocument; masthead: MastheadPlan }) {
  const { units, sources } = document.content;
  const split = sourceSplit(document);
  return (
    <div className="bx bx-mb">
      <section className="screen" data-aid="craft">
        <header className="kv-open">
          <div className="kv-wrap kv-open-grid">
            <div className="kv-open-q">
              {masthead.kicker ? <UnitView unit={units[masthead.kicker]} sources={sources} as="p" className="kicker kv-open-k" /> : null}
              <h1 className="kv-q">{document.title}</h1>
            </div>
            <div className="kv-open-a">
              {masthead.standfirst.map((ref) => (
                <UnitView key={ref} unit={units[ref]} sources={sources} as="p" className="kicker" />
              ))}
              {masthead.lede ? <UnitView unit={units[masthead.lede]} sources={sources} as="p" className="t-lede ans-lede" /> : null}
              <MastheadTools document={document} cite={citeAnchor(document, null)} />
              <OpenProvenance tally={gradeTally(document, split.own)} kin={split.kin.length} />
            </div>
            {masthead.picture ? <ComponentSlot document={document} label={masthead.picture} scoped={false} /> : null}
          </div>
        </header>
      </section>
    </div>
  );
}
