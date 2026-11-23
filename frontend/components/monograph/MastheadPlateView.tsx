import { TypographicPlate } from "@/components/editorial/TypographicPlate";
import { focalPosition } from "@/components/monograph/kinds/plates/SpecPicture";
import { unitNodes } from "@/components/monograph/UnitView";
import { isCommonsFile } from "@/lib/commonsPicture";
import type { MonographDocument } from "@/lib/monographDocument";
import { titleSize, type DocumentLabel, type MastheadPlate } from "@/lib/monographMasthead";
import { pictureSources } from "@/lib/pictureSources";

const SEAL_PATH = "M16.00 1.58 L20.23 5.80 L26.20 5.80 L26.20 11.77 L30.42 16.00 L26.20 20.23 L26.20 26.20 L20.23 26.20 L16.00 30.42 L11.77 26.20 L5.80 26.20 L5.80 20.23 L1.58 16.00 L5.80 11.77 L5.80 5.80 L11.77 5.80 Z";

function Seal() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path fill="none" stroke="currentColor" strokeWidth="1.8" d={SEAL_PATH} />
      <circle cx="16" cy="16" r="4" fill="currentColor" />
    </svg>
  );
}

function LabelCard({ view }: { view: DocumentLabel }) {
  return (
    <div className="label-card mast-label on-photo kv-open-label" data-size={titleSize(view.name)}>
      <p className="lc-k">
        <span>{view.kicker}</span>
        {view.family ? <span>{view.family}</span> : null}
      </p>
      <p className="lc-title">{view.name}</p>
      {view.gi || view.place ? (
        <div className="lc-meta">
          {view.gi ? (
            <span className="seal">
              <Seal />
              <span>{view.gi}</span>
            </span>
          ) : null}
          {view.place ? <span>{view.place}</span> : null}
        </div>
      ) : null}
    </div>
  );
}

function Photo({ plate }: { plate: MastheadPlate }) {
  const { picture } = plate;
  const sources = pictureSources(picture.src, "masthead", picture.width);
  return (
    <div className="ph">
      {/* eslint-disable-next-line @next/next/no-img-element -- the masthead photograph is offered at the standard Commons widths, as the approved page draws it */}
      <img
        src={sources.src}
        srcSet={sources.srcSet}
        sizes={sources.sizes}
        width={picture.width}
        height={picture.height}
        alt={picture.alt}
        loading="eager"
        fetchPriority="high"
        decoding="async"
        referrerPolicy="no-referrer"
        crossOrigin={isCommonsFile(sources.src) ? "anonymous" : undefined}
        style={picture.focal ? { objectPosition: focalPosition(picture) } : undefined}
      />
    </div>
  );
}

function Caption({ document, plate }: { document: MonographDocument; plate: MastheadPlate }) {
  const { units, sources } = document.content;
  return (
    <figcaption>
      {plate.captions
        .filter((line) => Object.hasOwn(units, line.unit))
        .map((line) => (
          <p key={line.unit} className={line.look ? "cap kv-look" : "cap"}>
            {unitNodes(units[line.unit], sources)}
          </p>
        ))}
      {Object.hasOwn(units, plate.credit) ? <p className="credit">{unitNodes(units[plate.credit], sources)}</p> : null}
    </figcaption>
  );
}

export function MastheadPlateView({ document, view }: { document: MonographDocument; view: DocumentLabel }) {
  if (!view.plate) {
    return (
      <div className="plate kv-open-photo">
        <div className="kv-open-stage">
          <div className="ph" data-app="">
            <TypographicPlate material={view.material} englishName={view.name} kicker={view.plateKicker} size="masthead" decorative />
          </div>
          <LabelCard view={view} />
        </div>
      </div>
    );
  }
  return (
    <figure className="plate kv-open-photo">
      <div className="kv-open-stage">
        <Photo plate={view.plate} />
        <LabelCard view={view} />
      </div>
      <Caption document={document} plate={view.plate} />
    </figure>
  );
}
