"use client";

import { useCallback, useMemo, useState } from "react";

import { AnswerFigure } from "@/components/answer/place/AnswerFigure";
import { AnswerMapSource } from "@/components/answer/place/AnswerMapSource";
import { MapPlaceholder } from "@/components/answer/place/MapPlaceholder";
import { RiverStage, type StageFocus } from "@/components/answer/place/RiverStage";
import { StoryKey, StoryLayerPicker } from "@/components/answer/place/StoryKey";
import { shownLayerFill, storyLayerInView } from "@/components/answer/place/storyLayer";
import { StoryLayerReadout } from "@/components/answer/place/StoryLayerReadout";
import { storyGeometry, storyTone, type StoryGeometry } from "@/components/answer/place/storyGeometry";
import { StorySteps } from "@/components/answer/place/StorySteps";
import { useRiverFlow, type RiverFlow } from "@/components/answer/place/useRiverFlow";
import { useStoryLayer, type StoryLayer } from "@/components/answer/place/useStoryLayer";
import { DatasetCredit } from "@/components/DatasetCredit";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { useRemote, type Remote } from "@/components/hooks/useRemote";
import type { DistrictFill } from "@/components/map/DistrictLayer";
import { IndiaLocator, LOCATOR_INSET, locatorLabel } from "@/components/map/IndiaLocator";
import { MapRetry } from "@/components/map/MapRetry";
import { loadShapes, type DistrictShape } from "@/components/map/shapeGeometry";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { HYDRORIVERS_DATASET_CODE, type RegionStoryBlock, type RiverPath } from "@/lib/explainerPlace";
import { boundaryNote, datasetRow, isGone } from "@/lib/placeView";
import type { MapLayer } from "@/lib/regionContract";
import { ALL_PASSED, missingReaches, playingStep, storySummary, storyTitle } from "@/lib/regionStory";
import { fetchRiverBasin, type RiverBasin } from "@/lib/riverTopology";
import { ShapeError } from "@/lib/shape";

const NO_THRESHOLDS: readonly number[] = [];
export const FOLLOW_THE_WATER = "Follow the water";

function useStoryBasin(river: RiverPath | null): Remote<RiverBasin> {
  const mainRiv = river?.mainRiv ?? null;
  const reachIds = river?.reachIds;
  const load = useCallback(async () => {
    const basin = await fetchRiverBasin(mainRiv as number);
    const missing = missingReaches(reachIds ?? [], basin.reaches);
    if (missing.length > 0) throw new ShapeError(`river ${mainRiv}`, `reaches ${missing.join(", ")} in its basin`);
    return basin;
  }, [mainRiv, reachIds]);
  return useRemote(mainRiv === null ? null : load);
}

function useStoryFill(geometry: StoryGeometry | null, story: StoryLayer, passed: number): { fillOf: DistrictFill; shown: MapLayer | null } {
  const data = story.layer.data;
  const shown = useMemo(() => (data && geometry ? storyLayerInView(geometry, data) : null), [data, geometry]);
  const layered = useMemo(() => (shown ? shownLayerFill(shown) : null), [shown]);
  const fillOf = useCallback(
    (shape: DistrictShape) => {
      if (layered) return layered(shape);
      return geometry ? storyTone(geometry, shape.lgd, passed) : null;
    },
    [layered, geometry, passed]
  );
  return { fillOf, shown };
}

function StoryLocator({ block, geometry }: { block: RegionStoryBlock; geometry: StoryGeometry }) {
  const marked = useMemo(() => [...geometry.districts.values()].map((district) => district.shape), [geometry]);
  return (
    <div className={LOCATOR_INSET} data-testid="story-locator">
      <IndiaLocator marked={marked} frame={geometry.view} label={locatorLabel(block.districts)} />
    </div>
  );
}

function StoryTools({ story, flow, base }: { story: StoryLayer; flow: RiverFlow; base: string }) {
  if (story.offered.length === 0 && !flow.replay) return null;
  return (
    <div className="mb-3 flex min-w-0 flex-wrap items-center justify-between gap-3">
      <StoryLayerPicker story={story} base={base} />
      {flow.replay ? (
        <ActionGroup align="start" inline>
          <Button variant="quiet" size="sm" onClick={flow.replay} data-testid="story-follow">
            {FOLLOW_THE_WATER}
          </Button>
        </ActionGroup>
      ) : null}
    </div>
  );
}

function flowStatus(flow: RiverFlow): string {
  if (!flow.moving) return "";
  return flow.passed >= ALL_PASSED ? "The water has reached every district in the story." : "The water is flowing downstream.";
}

function useStoryFocus(block: RegionStoryBlock, geometry: StoryGeometry | null, flow: RiverFlow): { focus: StageFocus; step: number | null } {
  const [selected, setSelected] = useState<number | null>(null);
  const fractions = geometry?.fractions ?? block.steps.map(() => ALL_PASSED);
  const step = selected ?? playingStep(fractions, flow.passed);
  const focus: StageFocus = {
    district: step === null ? null : block.steps[step].districtLgd,
    stretch: selected !== null,
    reached: fractions.map((fraction) => fraction <= flow.passed),
    onStep: (index) => setSelected((current) => (current === index ? null : index))
  };
  return { focus, step };
}

function StoryMap({ block, shapes, basin, view }: { block: RegionStoryBlock; shapes: Remote<DistrictShape[]>; basin: Remote<RiverBasin>; view: { geometry: StoryGeometry | null; flow: RiverFlow; story: StoryLayer; focus: StageFocus; waiting: boolean } }) {
  const { geometry, flow, story, focus, waiting } = view;
  const { fillOf, shown } = useStoryFill(geometry, story, flow.passed);
  const hydro = datasetRow(block.datasets, HYDRORIVERS_DATASET_CODE);
  const source = <AnswerMapSource boundary={boundaryNote(block.boundaryCaption, block.datasets)} />;
  return (
    <AnswerFigure texts={{ title: storyTitle(block), source }} className="lg:sticky lg:top-24">
      <StoryTools story={story} flow={flow} base={block.river ? "Water" : "Districts"} />
      {shapes.failure ? <MapRetry message="The map could not be drawn. Try again in a moment." onRetry={shapes.retry} /> : null}
      {geometry ? <RiverStage geometry={geometry} flow={flow} fillOf={fillOf} focus={focus} summary={storySummary(block)} inset={<StoryLocator block={block} geometry={geometry} />} /> : waiting && !shapes.failure ? <MapPlaceholder /> : null}
      <p role="status" className="sr-only">
        {flowStatus(flow)}
      </p>
      {geometry ? <StoryKey block={block} geometry={geometry} layered={shown !== null} /> : null}
      {basin.failure && !isGone(basin.failure) ? <MapRetry message="The river could not be drawn. Try again in a moment." onRetry={basin.retry} className="mt-3" /> : null}
      <StoryLayerReadout block={block} story={story} shown={shown} shapes={shapes} />
      {geometry?.river && hydro ? (
        <div className="mt-3">
          <DatasetCredit dataset={hydro} />
        </div>
      ) : null}
    </AnswerFigure>
  );
}

export function RegionStory({ block }: { block: RegionStoryBlock }) {
  const reduce = useAppReducedMotion();
  const shapes = useRemote(loadShapes);
  const basin = useStoryBasin(block.river);
  const geometry = useMemo(() => (shapes.data ? storyGeometry(block, shapes.data, basin.data) : null), [block, shapes.data, basin.data]);
  const expected = block.river !== null && basin.failure === null && shapes.failure === null;
  const flow = useRiverFlow(geometry?.thresholds ?? NO_THRESHOLDS, { expected, drawn: Boolean(geometry?.river) }, reduce);
  const story = useStoryLayer(block.layers);
  const { focus, step } = useStoryFocus(block, geometry, flow);
  const waiting = shapes.data === null || (block.river !== null && basin.data === null && basin.failure === null);
  const mapped = geometry !== null || waiting || shapes.failure !== null;
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:items-start lg:gap-10" data-testid="region-story">
      {mapped ? <StoryMap block={block} shapes={shapes} basin={basin} view={{ geometry, flow, story, focus, waiting }} /> : null}
      <StorySteps block={block} focus={focus} step={step} />
    </div>
  );
}
