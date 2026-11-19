"use client";

import { useState } from "react";

import { PictureView } from "@/components/answer/ImageStrip";
import { ZoomDistrict } from "@/components/answer/journey/ZoomDistrict";
import { MoleculeView } from "@/components/answer/matter/MoleculeView";
import { READING_PROSE } from "@/components/answer/place/figureMarks";
import { CitedText } from "@/components/answer/ProseBlockView";
import type { MediaRef } from "@/lib/explainerBlockBase";
import type { ZoomLevel, ZoomStoryBlock } from "@/lib/explainerPlay";
import { boundaryNote } from "@/lib/placeView";
import { zoomLevelLine, zoomLevelName, zoomMolecule } from "@/lib/zoomView";

function LevelPicture({ media }: { media: MediaRef }) {
  const [broken, setBroken] = useState(false);
  if (broken) return null;
  return <PictureView media={media} onBroken={() => setBroken(true)} />;
}

function LevelVisual({ block, level, moving }: { block: ZoomStoryBlock; level: ZoomLevel; moving: boolean }) {
  if (level.district) {
    const boundary = block.boundaryCaption ? boundaryNote(block.boundaryCaption, block.datasets) : null;
    return <ZoomDistrict district={level.district} boundary={boundary} moving={moving} />;
  }
  if (level.media) return <LevelPicture media={level.media} />;
  if (level.compound) return <MoleculeView block={zoomMolecule(block.id, level.compound)} />;
  return null;
}

export function ZoomLevelView({ block, index, moving }: { block: ZoomStoryBlock; index: number; moving: boolean }) {
  const level = block.levels[index];
  if (!level) return null;
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3" data-testid="zoom-level" data-level={level.level}>
      <div className="min-w-0">
        <p className="kicker">{zoomLevelLine(level, index, block.levels.length)}</p>
        {level.compound ? null : <h3 className="mt-1 break-words font-reading text-h3 text-ink-1">{zoomLevelName(level)}</h3>}
      </div>
      <LevelVisual block={block} level={level} moving={moving} />
      <CitedText id={level.sentence.id} sentences={[level.sentence]} className={READING_PROSE} />
    </div>
  );
}
