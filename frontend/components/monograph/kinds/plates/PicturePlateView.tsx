import type { ReactNode } from "react";

import { picturePlateShape, type ChapterOpener, type Picture, type PlateFigure } from "@/lib/componentSpecsPlates";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { parseShape } from "@/lib/shape";

import { HeldOrUnitText } from "./HeldText";
import { PlateMasthead } from "./PlateMasthead";
import { SpecPicture } from "./SpecPicture";

type RenderUnit = ComponentViewProps["renderUnit"];

function classList(...names: (string | null | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}

function PlateFigureView({ picture, figure, stage, renderUnit }: { picture: Picture; figure: PlateFigure; stage: ReactNode; renderUnit: RenderUnit }) {
  const frame = (
    <div className={classList("ph", figure.crop)}>
      <SpecPicture picture={picture} />
    </div>
  );
  return (
    <figure className={classList("plate", stage ? "kv-open-photo" : null, ...figure.classes)}>
      {stage ? (
        <div className="kv-open-stage">
          {frame}
          {stage}
        </div>
      ) : (
        frame
      )}
      <figcaption>
        {figure.captions.map((line) => (
          <p key={line.unit} className={line.look ? "cap kv-look" : "cap"}>
            {renderUnit(line.unit)}
          </p>
        ))}
        <p className="credit">{renderUnit(figure.credit)}</p>
      </figcaption>
    </figure>
  );
}

function PlateOpener({ picture, opener, renderUnit }: { picture: Picture; opener: ChapterOpener; renderUnit: RenderUnit }) {
  return (
    <div className="opener chapter-photo">
      <div className="op-ph">
        <SpecPicture picture={picture} />
      </div>
      <div className="wrap">
        <div className="op-label">
          <p className="chapter-no">{renderUnit(opener.chapterNo)}</p>
          <p className="kicker op-kicker">{renderUnit(opener.kicker)}</p>
          <h2 className="t-h2" id={opener.titleId}>
            {renderUnit(opener.title)}
          </h2>
          <p className="op-dek">{renderUnit(opener.dek)}</p>
        </div>
        <p className="op-credit">{renderUnit(opener.credit)}</p>
      </div>
    </div>
  );
}

export function PicturePlateView({ spec, renderUnit }: ComponentViewProps) {
  const plate = parseShape(picturePlateShape, spec);
  if (plate.opener) return <PlateOpener picture={plate.picture} opener={plate.opener} renderUnit={renderUnit} />;
  if (!plate.figure) throw new RangeError(`A ${plate.setting} plate frames its picture as a figure`);
  const stage = plate.masthead ? <PlateMasthead label={plate.masthead} renderUnit={renderUnit} /> : null;
  const figure = <PlateFigureView picture={plate.picture} figure={plate.figure} stage={stage} renderUnit={renderUnit} />;
  if (plate.row) {
    return (
      <div className={classList("plate-row", ...plate.row.classes)}>
        {figure}
        <div>
          <p className="note-p">{renderUnit(plate.row.note)}</p>
        </div>
      </div>
    );
  }
  if (plate.pull) {
    return (
      <div className={plate.pull.classes.join(" ")}>
        {figure}
        <div className={plate.pull.box}>
          <blockquote className="kv-pull">
            <p>{renderUnit(plate.pull.quote)}</p>
            <footer>
              <HeldOrUnitText value={plate.pull.attribution} renderUnit={renderUnit} />
            </footer>
          </blockquote>
        </div>
      </div>
    );
  }
  return figure;
}
