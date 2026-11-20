import { Fragment } from "react";

import { Masthead, type MastheadPicture } from "@/components/editorial/Masthead";
import { provenanceLine } from "@/components/monograph/MonographMasthead";
import { MARGIN_LABEL } from "@/components/monograph/MonographPassage";
import { reliabilityFill } from "@/lib/citationCluster";
import type { MonographDocument } from "@/lib/monographDocument";
import { documentLabel, LEDE_KICKER, ledeNotes, type MastheadPhoto } from "@/lib/monographMasthead";
import { nodeElements } from "@/lib/monographRenderElements";
import type { GradeTally } from "@/lib/monographRenderKit";
import type { LabelMasthead } from "@/lib/monographRenderLayout";
import type { SourceReliability } from "@/lib/types";

function Provenance({ tally }: { tally: GradeTally }) {
  const words = provenanceLine(tally);
  return (
    <span className="kv-prov">
      <span>{words.drawn}</span>
      {tally.grades.length ? (
        <span className="kv-rel-strip" role="img" aria-label={words.reliability}>
          {tally.grades.map((found) => (
            <span key={found.grade} className="kv-rel-count" aria-hidden>
              <span className="kv-rel" data-grade={found.grade} data-fill={reliabilityFill(found.grade as SourceReliability)} />
              {`${found.grade} ${found.count}`}
            </span>
          ))}
        </span>
      ) : null}
    </span>
  );
}

function shownPicture(photo: MastheadPhoto | null): MastheadPicture | null {
  if (!photo) return null;
  return { src: photo.src, alt: photo.alt, caption: photo.caption, credit: photo.credit, wide: photo.focal, narrow: photo.focal, originalWidth: photo.originalWidth };
}

function LedeSpread({ document, lede }: { document: MonographDocument; lede: readonly string[] }) {
  const { units, sources } = document.content;
  const notes = ledeNotes(document, lede);
  return (
    <div className="bx bx-mb">
      <div className="screen" data-aid="craft">
        <div className="wrap kv-mlede">
          <div className="spread mast-lede">
            <div className="rail">
              <p className="lede-k">{LEDE_KICKER}</p>
            </div>
            <div className="main">
              <p className="t-lede">
                {lede.map((ref, at) => (
                  <Fragment key={ref}>
                    {at ? " " : null}
                    {nodeElements(units[ref].nodes, sources)}
                  </Fragment>
                ))}
              </p>
            </div>
            {notes.length ? (
              <aside className="margin note" aria-label={MARGIN_LABEL}>
                <ul>
                  {notes.map((note) => (
                    <li key={note.key} data-g={note.key}>
                      <b>{note.number}</b>
                      <span>{note.year ? `${note.title}, ${note.year}` : note.title}</span>
                    </li>
                  ))}
                </ul>
              </aside>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

export function DocumentMasthead({ document, label }: { document: MonographDocument; label: LabelMasthead }) {
  const view = documentLabel(document, label);
  return (
    <>
      <div className="kv-page kv-doc-open" data-app="">
        <Masthead
          material={view.material}
          plateKicker={view.plateKicker}
          picture={shownPicture(view.photo)}
          label={{ kicker: view.kicker, family: view.family, name: view.name, gi: view.gi, place: view.place, provenance: view.tally.total ? <Provenance tally={view.tally} /> : undefined }}
        />
      </div>
      {label.lede.length ? <LedeSpread document={document} lede={label.lede} /> : null}
    </>
  );
}
