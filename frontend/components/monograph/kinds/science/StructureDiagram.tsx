import type { ComponentViewProps } from "@/lib/componentViewContract";
import { structureDiagramShape, type StructureDiagramSpec, type StructureMolecule } from "@/lib/componentSpecsScienceFigures";
import { parseShape } from "@/lib/shape";

import { CiteButton } from "@/components/monograph/kinds/plates/HeldText";
import { Drawing, RichText } from "./parts/Drawing";
import { Block, Blocks, FigureHeadLines, type RenderUnit } from "./parts/Text";

function Structure({ molecule, renderUnit }: { molecule: StructureMolecule; renderUnit: RenderUnit }) {
  return (
    <figure className="m anth">
      <Drawing node={molecule.drawing} />
      <figcaption>
        <b>{molecule.name}</b>
        <span className="m-f" dir="ltr">
          <RichText runs={molecule.formula} />
        </span>
        <span className="m-s">{molecule.note}</span>
        <dl className="m-dl">
          <dt>{renderUnit(molecule.atomsTerm)}</dt>
          <dd dir="ltr">{renderUnit(molecule.atoms)}</dd>
          <dt>{renderUnit(molecule.recordTerm)}</dt>
          <dd>
            <span lang="en" dir="ltr">{`PubChem CID ${molecule.cid}`}</span>
            {molecule.recordCite ? <CiteButton mark={molecule.recordCite} /> : null}
          </dd>
        </dl>
      </figcaption>
    </figure>
  );
}

function Side({ figure, renderUnit }: { figure: StructureDiagramSpec; renderUnit: RenderUnit }) {
  return (
    <div className="anth-side">
      <Blocks blocks={figure.notes} renderUnit={renderUnit} />
      <p className="m-key">
        <span className="m-sw" aria-hidden="true" />
        {figure.key}
      </p>
      {figure.swatches.length ? (
        <div className="whites">
          {figure.swatches.map((swatch) => (
            <div key={swatch.colour} className="wh">
              <span className="swatch" aria-hidden="true">
                <span className="sw-in" style={{ backgroundColor: `var(${swatch.colour})` }} />
              </span>
              <span>{swatch.label}</span>
            </div>
          ))}
          {figure.swatchNote ? <Block block={figure.swatchNote} renderUnit={renderUnit} /> : null}
        </div>
      ) : null}
    </div>
  );
}

export function StructureDiagram({ spec, renderUnit }: ComponentViewProps) {
  const figure = parseShape(structureDiagramShape, spec);
  return (
    <figure className="fig chemfig redfig" id={figure.id} aria-labelledby={figure.head.titleId ?? undefined}>
      <figcaption className="fig-head">
        <FigureHeadLines head={figure.head} renderUnit={renderUnit} dekStyle={figure.dekStyle} />
      </figcaption>
      <div className="anth-grid">
        <div className="anth-col">
          <p className="scale-k">{renderUnit(figure.scale)}</p>
          <div className="anth-pair">
            {figure.molecules.map((molecule) => <Structure key={molecule.cid} molecule={molecule} renderUnit={renderUnit} />)}
          </div>
        </div>
        <Side figure={figure} renderUnit={renderUnit} />
      </div>
    </figure>
  );
}
