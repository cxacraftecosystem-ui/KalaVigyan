import { Fragment } from "react";

import { MastheadPlateView } from "@/components/monograph/MastheadPlateView";
import { citeAnchor, MastheadTools, OpenProvenance } from "@/components/monograph/MonographMasthead";
import { unitNodes } from "@/components/monograph/UnitView";
import { documentCitation } from "@/lib/monographCite";
import type { MonographDocument } from "@/lib/monographDocument";
import { documentLabel, LEDE_KICKER } from "@/lib/monographMasthead";
import type { LabelMasthead } from "@/lib/monographRenderLayout";

export const PAGE_CITATION_ID = "kv-cite-this";

function Lede({ document, lede }: { document: MonographDocument; lede: readonly string[] }) {
  const { units, sources } = document.content;
  if (!lede.length) return null;
  return (
    <>
      <p className="kicker">{LEDE_KICKER}</p>
      <p className="t-lede ans-lede">
        {lede.map((ref, at) => (
          <Fragment key={ref}>
            {at ? " " : null}
            {unitNodes(units[ref], sources)}
          </Fragment>
        ))}
      </p>
    </>
  );
}

export function KitMasthead({ document, label }: { document: MonographDocument; label: LabelMasthead }) {
  const view = documentLabel(document, label);
  const cite = citeAnchor(document, documentCitation(document) ? `#${PAGE_CITATION_ID}` : null);
  return (
    <div className="bx bx-mb">
      <section className="screen" data-aid="craft">
        <header className="kv-open">
          <div className="kv-wrap kv-open-grid">
            <div className="kv-open-q">
              <p className="kicker kv-open-k">
                <span>{view.kicker}</span>
              </p>
              <h1 className="kv-q">{view.name}</h1>
            </div>
            <div className="kv-open-a">
              <Lede document={document} lede={label.lede} />
              <MastheadTools document={document} cite={cite} />
              <OpenProvenance tally={view.tally} kin={view.kin} />
            </div>
            <MastheadPlateView document={document} view={view} />
          </div>
        </header>
      </section>
    </div>
  );
}
