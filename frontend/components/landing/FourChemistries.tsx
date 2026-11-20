"use client";

import { Fragment, useId } from "react";

import { SourcesDifferNote } from "@/components/editorial/EvidenceMark";
import { CitedText, type CiteMaps } from "@/components/landing/CitedText";
import { dye, type Dye } from "@/components/landing/clothTile";
import type { ColourKey, LandingColour, LandingContent } from "@/components/landing/landingContent";

type Swatch = { dye: Dye; caption: string };

type ColourView = { title: string; local: string; agent: string; pair: readonly [Swatch, Swatch]; versus: boolean };

export const COLOUR_VIEWS: Record<ColourKey, ColourView> = {
  blue: { title: "Blue", local: "vadali, neela", agent: "Indigo, then air", pair: [{ dye: "leuco", caption: "lifted" }, { dye: "indigo", caption: "in air" }], versus: false },
  black: { title: "Black", local: "kalo", agent: "Iron on tannin", pair: [{ dye: "harda", caption: "harda" }, { dye: "kut", caption: "kut printed" }], versus: false },
  red: { title: "Red", local: "laal", agent: "Madder on alum", pair: [{ dye: "kesari", caption: "pa printed" }, { dye: "madder", caption: "after rang" }], versus: false },
  white: { title: "White", local: "safed, dhodo", agent: "Lime keeps it", pair: [{ dye: "lime", caption: "under lime" }, { dye: "pink", caption: "open cloth" }], versus: true }
};

function SwatchFigure({ swatch, weave }: { swatch: Swatch; weave: string }) {
  return (
    <figure>
      <span className="kv-swatch">
        <svg viewBox="0 0 80 80" aria-hidden focusable="false">
          <rect width="80" height="80" fill={dye(swatch.dye)} />
          <rect width="80" height="80" fill={`url(#${weave})`} />
        </svg>
      </span>
      <figcaption>{swatch.caption}</figcaption>
    </figure>
  );
}

function Colour({ colour, cite, weave, named }: { colour: LandingColour; cite: CiteMaps; weave: string; named: boolean }) {
  const view = COLOUR_VIEWS[colour.key];
  return (
    <li className="kv-colour">
      <div className="kv-pair">
        <SwatchFigure swatch={view.pair[0]} weave={weave} />
        <span className="kv-pair-arrow" aria-hidden data-vs={view.versus ? "" : undefined}>
          {view.versus ? "or" : "→"}
        </span>
        <SwatchFigure swatch={view.pair[1]} weave={weave} />
      </div>
      <h3>
        {view.title}
        {named ? <i>{view.local}</i> : null}
      </h3>
      <p className="kv-colour-agent">{view.agent}</p>
      <p className="kv-colour-text">
        {colour.sentences.map((sentence, index) => (
          <Fragment key={sentence.id}>
            {index > 0 ? " " : null}
            <CitedText sentence={sentence} cite={cite} />
          </Fragment>
        ))}
      </p>
    </li>
  );
}

export function FourChemistries({ content, cite }: { content: LandingContent; cite: CiteMaps }) {
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const weave = `kv-swatch-weave${id}`;
  if (content.colours.length === 0) return null;
  return (
    <section className="kv-four" aria-labelledby={`${weave}-h`}>
      <svg width="0" height="0" className="absolute" aria-hidden focusable="false">
        <defs>
          <pattern id={weave} width="3" height="3" patternUnits="userSpaceOnUse">
            <path d="M0 3 L3 0" stroke={dye("kut")} strokeOpacity="0.07" strokeWidth="0.6" />
            <path d="M0 0 L3 3" stroke={dye("cloth")} strokeOpacity="0.06" strokeWidth="0.5" />
          </pattern>
        </defs>
      </svg>
      <div className="kv-shell-wrap">
        <div className="kv-four-head">
          <div>
            <p className="kv-chapter-no">{`${content.name}, read closely`}</p>
            <h2 id={`${weave}-h`} className="m-0 font-headline text-h2 text-ink-1">
              One cloth, four chemistries
            </h2>
          </div>
          {content.intro ? (
            <p className="kv-four-intro">
              <CitedText sentence={content.intro} cite={cite} />
            </p>
          ) : null}
        </div>
        <ul className="kv-colours">
          {content.colours.map((colour) => (
            <Colour key={colour.key} colour={colour} cite={cite} weave={weave} named={content.meanings !== null} />
          ))}
        </ul>
        <ColourKey content={content} cite={cite} />
      </div>
    </section>
  );
}

function ColourKey({ content, cite }: { content: LandingContent; cite: CiteMaps }) {
  if (!content.meanings && !content.differ) return null;
  return (
    <div className="kv-colour-key">
      {content.meanings ? (
        <p>
          <CitedText sentence={content.meanings} cite={cite} />
        </p>
      ) : null}
      {content.differ ? (
        <SourcesDifferNote on summary="what the colours mean">
          <CitedText sentence={content.differ} cite={cite} />
        </SourcesDifferNote>
      ) : null}
    </div>
  );
}
