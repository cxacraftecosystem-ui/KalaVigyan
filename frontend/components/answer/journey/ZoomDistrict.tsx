"use client";

import { useCallback, useMemo } from "react";

import { districtFrame } from "@/components/answer/journey/journeyGeometry";
import { AnswerFigure } from "@/components/answer/place/AnswerFigure";
import { AnswerMapSource } from "@/components/answer/place/AnswerMapSource";
import { MapPlaceholder } from "@/components/answer/place/MapPlaceholder";
import { useRemote } from "@/components/hooks/useRemote";
import { DistrictFills, DistrictOutlines, DistrictTag, HIGHLIGHT_TONES } from "@/components/map/DistrictLayer";
import { IndiaLocator, LOCATOR_INSET, locatorLabel } from "@/components/map/IndiaLocator";
import { IndiaMap } from "@/components/map/IndiaMap";
import { MapRetry } from "@/components/map/MapRetry";
import { loadShapes, type DistrictShape } from "@/components/map/shapeGeometry";
import type { DistrictRef } from "@/lib/explainerPlace";
import type { BoundaryNote } from "@/lib/regionContract";

const NO_POINTS: never[] = [];
const QUIET_TONE = "fill-transparent";
const AT_REST = { scale: 1, x: "0%", y: "0%" };

type ZoomMapProps = { shapes: DistrictShape[]; district: DistrictRef; boundary: BoundaryNote | null; moving: boolean };

export function ZoomDistrictMap({ shapes, district, boundary, moving }: ZoomMapProps) {
  const shape = useMemo(() => shapes.find((entry) => entry.lgd === district.districtLgd) ?? null, [shapes, district.districtLgd]);
  const fillOf = useCallback((entry: DistrictShape) => (entry.lgd === district.districtLgd ? HIGHLIGHT_TONES.district : QUIET_TONE), [district.districtLgd]);
  const frame = useMemo(() => districtFrame(shape), [shape]);
  if (!shape) return null;
  const target = moving ? frame : AT_REST;
  const marks = (
    <>
      <DistrictOutlines shapes={[shape]} className="stroke-terracotta" />
      <DistrictTag shape={shape} text={district.name} />
    </>
  );
  return (
    <AnswerFigure texts={{ source: <AnswerMapSource boundary={boundary} /> }} data-testid="zoom-district" data-lgd={district.districtLgd} data-scale={target.scale}>
      <div className="relative overflow-hidden rounded-plate [forced-color-adjust:none]">
        <div style={{ transformOrigin: "0% 0%", transform: `translateX(${target.x}) translateY(${target.y}) scale(${target.scale})` }}>
          <IndiaMap points={NO_POINTS} underlay={<DistrictFills shapes={shapes} fillOf={fillOf} />} overlay={marks} />
        </div>
        {target.scale > 1 ? (
          <div className={LOCATOR_INSET} data-testid="zoom-locator">
            <IndiaLocator marked={[shape]} frame={null} label={locatorLabel([district])} />
          </div>
        ) : null}
      </div>
    </AnswerFigure>
  );
}

export function ZoomDistrict({ district, boundary, moving }: { district: DistrictRef; boundary: BoundaryNote | null; moving: boolean }) {
  const shapes = useRemote(loadShapes);
  if (shapes.failure) return <MapRetry message="The map could not be drawn. Try again in a moment." onRetry={shapes.retry} />;
  if (!shapes.data) return <MapPlaceholder />;
  return <ZoomDistrictMap shapes={shapes.data} district={district} boundary={boundary} moving={moving} />;
}
