import type { ReactNode } from "react";

import { voiceShape, type VoiceCoda, type VoiceTestimony } from "@/lib/componentSpecsPlates";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { parseShape } from "@/lib/shape";

import { HeldOrUnitText } from "./HeldText";

type RenderUnit = (ref: string) => ReactNode;

const CLOTH_BLEED = 100;

function Testimony({ voice, renderUnit }: { voice: VoiceTestimony; renderUnit: RenderUnit }) {
  return (
    <figure className="voice" aria-labelledby={voice.kickerId}>
      <div className="voice-top">
        <p className="kicker" id={voice.kickerId}>
          {renderUnit(voice.kicker)}
        </p>
        <p className="voice-ev">
          <span className="t-mark" aria-hidden="true"></span>
          {voice.evidence}
        </p>
      </div>
      <blockquote className="voice-q">
        <p>{renderUnit(voice.quote)}</p>
      </blockquote>
      <figcaption className="voice-cap">
        <p className="voice-credit">{renderUnit(voice.credit)}</p>
        <p className="voice-meta">{renderUnit(voice.meta)}</p>
      </figcaption>
      {voice.echo ? (
        <blockquote className="voice-q2">
          <p>{renderUnit(voice.echo.quote)}</p>
          <footer>
            <HeldOrUnitText value={voice.echo.attribution} renderUnit={renderUnit} />
          </footer>
        </blockquote>
      ) : null}
    </figure>
  );
}

function Coda({ coda, renderUnit }: { coda: VoiceCoda; renderUnit: RenderUnit }) {
  const [, , width, height] = coda.viewBox.split(" ").map(Number);
  const bleed = { x: -CLOTH_BLEED, y: -CLOTH_BLEED, width: width + 2 * CLOTH_BLEED, height: height + 2 * CLOTH_BLEED };
  return (
    <section className="kv-coda" aria-label={coda.label}>
      <svg className="kv-coda-cloth" viewBox={coda.viewBox} preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
        <rect {...bleed} fill={`url(#${coda.tile})`} />
        <rect {...bleed} fill={`url(#${coda.weave})`} />
      </svg>
      <div className="kv-wrap kv-coda-in">
        <figure className="label-card kv-coda-card">
          <p className="lc-k">{renderUnit(coda.kicker)}</p>
          <blockquote className="kv-coda-q">
            <p>{renderUnit(coda.quote)}</p>
          </blockquote>
          <figcaption className="kv-coda-c">{renderUnit(coda.caption)}</figcaption>
          <p className="kv-coda-n">{renderUnit(coda.note)}</p>
        </figure>
      </div>
    </section>
  );
}

export function VoiceView({ spec, renderUnit }: ComponentViewProps) {
  const voice = parseShape(voiceShape, spec);
  if (voice.testimony) return <Testimony voice={voice.testimony} renderUnit={renderUnit} />;
  if (voice.coda) return <Coda coda={voice.coda} renderUnit={renderUnit} />;
  throw new RangeError(`A ${voice.setting} voice has its part`);
}
