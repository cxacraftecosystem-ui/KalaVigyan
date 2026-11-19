"use client";

import { useEffect, useState } from "react";
import { animate, useMotionValue, useMotionValueEvent, type MotionValue } from "framer-motion";

import { ALL_PASSED, FLOW_EASE, FLOW_SECONDS, NOT_YET, passedFraction } from "@/lib/regionStory";

export type RiverFlow = {
  progress: MotionValue<number>;
  moving: boolean;
  passed: number;
  replay: (() => void) | null;
};

export type FlowReadiness = { expected: boolean; drawn: boolean };

export function useRiverFlow(thresholds: readonly number[], river: FlowReadiness, reduce: boolean): RiverFlow {
  const progress = useMotionValue(ALL_PASSED);
  const [passed, setPassed] = useState(ALL_PASSED);
  const [round, setRound] = useState(0);
  const allowed = river.expected && river.drawn && !reduce;
  const moving = allowed && round > 0;

  useMotionValueEvent(progress, "change", (value) => {
    const next = passedFraction(thresholds, value);
    setPassed((current) => (current === next ? current : next));
  });

  useEffect(() => {
    if (!moving) return;
    progress.jump(0);
    setPassed(NOT_YET);
    const controls = animate(progress, ALL_PASSED, { duration: FLOW_SECONDS, ease: [...FLOW_EASE] });
    return () => controls.stop();
  }, [moving, round, progress]);

  const shown = moving ? passed : ALL_PASSED;
  const replay = allowed && shown >= ALL_PASSED ? () => setRound((value) => value + 1) : null;
  return { progress, moving, passed: shown, replay };
}
