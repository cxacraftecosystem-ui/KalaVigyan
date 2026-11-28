import { KitSceneArt, KitSceneKey } from "@/components/artkit/KitScene";
import type { KitIds } from "@/components/artkit/kitIds";
import { isKitScene, type KitScene } from "@/lib/componentSpecsKitScene";
import type { SvgNode } from "@/lib/componentSpecsScienceParts";
import type { StageEntry, StagePlayerSpec } from "@/lib/componentSpecsSciencePlayers";

import { Drawing } from "./parts/Drawing";
import { NoteDiffers } from "./parts/Differs";
import { StageTile } from "./parts/icons";
import type { RenderUnit } from "./parts/Text";

export const STORED_AFTER_LABEL = "Cloth after";
export const SCENE_CLASS = "kv-kit-scene";

export const afterLabel = (player: StagePlayerSpec) => player.afterLabel ?? STORED_AFTER_LABEL;

export const stageSceneName = (stage: number) => `stage-${stage}`;

type StageProps = { entry: StageEntry; stage: number; rest: boolean; prefix: string; label: string; ids: KitIds; renderUnit: RenderUnit };
type SceneProps = { scene: SvgNode | KitScene; stage: number; ids: KitIds; renderUnit: RenderUnit };

export function drawnStageScene(node: SvgNode, stage: number): SvgNode {
  const attrs = node.attrs ?? {};
  const shown = attrs.class ? `${attrs.class} ${SCENE_CLASS}` : SCENE_CLASS;
  return { ...node, attrs: { ...attrs, class: shown, "aria-hidden": "true", "data-kit-scene": stageSceneName(stage) } };
}

function StageScene({ scene, stage, ids, renderUnit }: SceneProps) {
  if (!isKitScene(scene)) {
    return (
      <div className="lc-scene">
        <Drawing node={drawnStageScene(scene, stage)} />
      </div>
    );
  }
  return (
    <div className="lc-scene">
      <KitSceneArt scene={scene} ids={ids} name={stageSceneName(stage)} />
      <KitSceneKey scene={scene} ids={ids} renderUnit={renderUnit} />
    </div>
  );
}

function Stage({ entry, stage, rest, prefix, label, ids, renderUnit }: StageProps) {
  return (
    <li className="lc-step" id={`${prefix}-st-${stage}`} data-stage={stage} aria-current={rest ? "step" : undefined}>
      <div className="lc-sh">
        <span className="lc-tile">
          <StageTile stage={stage} style="lc-tsvg" viewBox="0 0 100 100" swatch={entry.swatch} />
        </span>
        <p className="lc-no">{renderUnit(entry.number)}</p>
        <h3>{renderUnit(entry.heading)}</h3>
      </div>
      {entry.scene ? <StageScene scene={entry.scene} stage={stage} ids={ids} renderUnit={renderUnit} /> : null}
      {entry.texts.map((unit) => <p key={unit} className="lc-t">{renderUnit(unit)}</p>)}
      {entry.why !== null ? <p className="lc-why">{renderUnit(entry.why)}</p> : null}
      {entry.differs !== null ? <NoteDiffers differs={entry.differs} renderUnit={renderUnit} /> : null}
      {entry.afterSentence !== null ? (
        <p className="lc-after">
          <span className="lk">{label}</span>
          <span className="lc-av">
            <StageTile stage={stage} style="lc-sw" viewBox="0 0 200 200" swatch={entry.swatch} />
            {renderUnit(entry.afterSentence)}
          </span>
        </p>
      ) : null}
      {entry.materials !== null ? <p className="lc-mats">{renderUnit(entry.materials)}</p> : null}
    </li>
  );
}

export function StageList({ player, ids, renderUnit }: { player: StagePlayerSpec; ids: KitIds; renderUnit: RenderUnit }) {
  const rest = player.stages.length;
  return (
    <ol className="lc-steps">
      {player.stages.map((entry, index) => (
        <Stage key={entry.name} entry={entry} stage={index + 1} rest={index + 1 === rest} prefix={player.key} label={afterLabel(player)} ids={ids} renderUnit={renderUnit} />
      ))}
    </ol>
  );
}

export function StageRibbon({ player }: { player: StagePlayerSpec }) {
  const rest = player.stages.length;
  return (
    <div className="lc-ribbon" role="toolbar" aria-label="Stages" aria-orientation="horizontal">
      {player.stages.map((entry, index) => {
        const stage = index + 1;
        return (
          <button
            key={entry.name}
            type="button"
            className="rb"
            data-go={stage}
            aria-pressed={stage === rest}
            tabIndex={stage === rest ? 0 : -1}
            aria-controls={`${player.key}-st-${stage}`}
            aria-label={`${stage} ${entry.name}`}
          >
            <StageTile stage={stage} style="rb-svg" viewBox="0 0 100 150" swatch={entry.swatch} />
            <span className="rb-l">
              <b>{stage}</b>
              {entry.local ? <i>{entry.name}</i> : <span>{entry.name}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
