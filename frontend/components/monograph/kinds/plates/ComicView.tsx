import { comicShape } from "@/lib/componentSpecsPlates";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { parseShape } from "@/lib/shape";

import { HeldOrUnitText } from "./HeldText";
import { panelCount } from "./mediaCopy";
import { SpecDrawing } from "./SpecDrawing";

export function ComicView({ spec, renderUnit }: ComponentViewProps) {
  const comic = parseShape(comicShape, spec);
  const total = comic.panels.length;
  return (
    <ol className="comic" data-role="comic" aria-label={comic.label}>
      {comic.panels.map((panel, index) => (
        <li key={index} className={panel.layout ? `panel ${panel.layout}` : "panel"} data-i={index + 1}>
          <figure className="pf">
            <figcaption className="pcap">
              <span className="pnum num-tab" aria-hidden="true">
                {index + 1}
              </span>
              <span className="vh">{panelCount(index + 1, total)}</span>
              <HeldOrUnitText value={panel.caption} renderUnit={renderUnit} />
            </figcaption>
            <div className="pan-box">
              <SpecDrawing element={panel.art} />
              <span className="ai-tag">{panel.tag}</span>
            </div>
          </figure>
        </li>
      ))}
    </ol>
  );
}
