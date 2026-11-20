import type { ComponentViewProps } from "@/lib/componentViewContract";
import { reactionPlayerShape, type ReactionPlayerSpec, type StepScene } from "@/lib/componentSpecsSciencePlayers";
import { parseShape } from "@/lib/shape";

import { Drawing, Drawings } from "./parts/Drawing";
import { PlayIcon } from "./parts/icons";
import { FigureHeadLines, type RenderUnit } from "./parts/Text";
import { ChemistryPartView } from "./ReactionChemistry";
import { ReactionStepText } from "./ReactionStepText";

function Rail({ player }: { player: ReactionPlayerSpec }) {
  return (
    <div className="rp-bar">
      <div className="rp-rail" role="group" aria-label="Steps">
        {player.steps.map((step, index) => {
          const pressed = index + 1 === player.current;
          return (
            <button key={step.name} type="button" aria-pressed={pressed} tabIndex={pressed ? 0 : -1} aria-label={`Step ${index + 1}, ${step.name}`}>
              <b>{index + 1}</b> <span aria-hidden="true">{step.name}</span>
            </button>
          );
        })}
      </div>
      <button className="btn sm rp-play" type="button" aria-pressed="false">
        <PlayIcon />
        <span>Play</span>
      </button>
    </div>
  );
}

function Reaction({ scene, step, shown, renderUnit }: { scene: StepScene; step: number; shown: boolean; renderUnit: RenderUnit }) {
  return (
    <div className="rx" data-i={step} hidden={!shown}>
      <div className="rx-where">
        <Drawing node={scene.whereIcon} />
        <p>{renderUnit(scene.where)}</p>
      </div>
      <div className="rx-art">
        <Drawings nodes={scene.art} />
      </div>
    </div>
  );
}

function Scene({ player, renderUnit }: { player: ReactionPlayerSpec; renderUnit: RenderUnit }) {
  return (
    <div className="rp-scene">
      <Drawings nodes={player.scenes} />
      {player.steps.map((step, index) =>
        step.scene ? <Reaction key={step.name} scene={step.scene} step={index + 1} shown={index + 1 === player.current} renderUnit={renderUnit} /> : null
      )}
      {player.key !== null ? (
        <p className="rx-key">
          <span className="rk" aria-hidden="true" />
          {player.key}
        </p>
      ) : null}
      <p className="rp-status" role="status" aria-live="polite">
        {renderUnit(player.status)}
      </p>
    </div>
  );
}

export function ReactionPlayer({ spec, renderUnit }: ComponentViewProps) {
  const player = parseShape(reactionPlayerShape, spec);
  const reacting = player.steps.some((step) => step.scene !== null);
  return (
    <figure className={reacting ? "rp rx-player" : "rp"} id={player.id} data-track={player.track} data-step={player.current} data-steps={player.steps.length}>
      <figcaption className="rp-cap">
        <FigureHeadLines head={player.head} renderUnit={renderUnit} />
      </figcaption>
      <Rail player={player} />
      <div className="rp-body">
        <Scene player={player} renderUnit={renderUnit} />
        <div className="rp-text">
          {player.steps.map((step, index) => (
            <ReactionStepText key={step.name} text={step.text} step={index + 1} shown={index + 1 === player.current} renderUnit={renderUnit} />
          ))}
        </div>
      </div>
      <div className="rp-chems">
        {player.steps.map((step, index) => (
          <div key={step.name} className="rp-chem" hidden={index + 1 !== player.current}>
            {step.chemistry.parts.map((part, at) => <ChemistryPartView key={at} part={part} renderUnit={renderUnit} />)}
          </div>
        ))}
      </div>
    </figure>
  );
}
