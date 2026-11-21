import type { ComponentViewProps } from "@/lib/componentViewContract";
import { stagePlayerShape, type StagePlayerSpec } from "@/lib/componentSpecsSciencePlayers";
import { parseShape } from "@/lib/shape";

import { Drawing } from "./parts/Drawing";
import { PlayStagesIcon } from "./parts/icons";
import { FigureHeadLines, type RenderUnit } from "./parts/Text";
import { afterLabel, StageList, StageRibbon } from "./StageList";

export const stagesForScript = (player: StagePlayerSpec) =>
  JSON.stringify(
    player.stages.map((entry, index) => ({ n: index + 1, name: entry.name, eng: entry.english, local: entry.local, after: entry.after }))
  );

function LabelCard({ player, renderUnit }: { player: StagePlayerSpec; renderUnit: RenderUnit }) {
  const rest = player.stages.length;
  return (
    <div className="label-card lc-label">
      <p className="lc-k">
        <span data-k="">{`Stage ${rest} of ${rest}`}</span>
      </p>
      <p className="lc-name" data-h="">
        {renderUnit(player.restName)}
      </p>
      <p className="lc-now">
        <span className="lk">{afterLabel(player)}</span>
        <span data-a="">{player.stages[rest - 1].after}</span>
      </p>
      <div className="lc-play">
        <div className="actions start" data-count="1">
          <button className="btn sm" type="button" data-play="" aria-pressed="false">
            <PlayStagesIcon />
            <span>{player.play}</span>
          </button>
        </div>
        <p className="lc-status" role="status" aria-live="polite" data-live="" />
      </div>
    </div>
  );
}

export function StagePlayer({ spec, renderUnit }: ComponentViewProps) {
  const player = parseShape(stagePlayerShape, spec);
  return (
    <figure className="fig lc-fig" aria-labelledby={player.head.titleId ?? undefined}>
      <FigureHeadLines head={player.head} renderUnit={renderUnit} />
      <div className="lc" data-comp="cloth" id={`${player.key}-lc`} data-rest={player.stages.length} data-stages={stagesForScript(player)}>
        <div className="lc-stagebox">
          <div className="lc-big" data-big="">
            <Drawing node={player.drawing} />
          </div>
          <LabelCard player={player} renderUnit={renderUnit} />
        </div>
        <StageRibbon player={player} />
        <p className="src-line lc-src">{renderUnit(player.source)}</p>
        <StageList player={player} renderUnit={renderUnit} />
        <div className="lc-fin">
          <h3>{renderUnit(player.finish.heading)}</h3>
          {player.finish.paragraphs.map((unit) => <p key={unit}>{renderUnit(unit)}</p>)}
        </div>
      </div>
    </figure>
  );
}
