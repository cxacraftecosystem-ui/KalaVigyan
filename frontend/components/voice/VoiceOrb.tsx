"use client";

import { useEffect } from "react";
import { motion, useMotionValue, useTransform } from "framer-motion";
import { AudioLines, LoaderCircle, Mic, MicOff, Send } from "lucide-react";

import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import type { Activity } from "@/lib/voiceCall";
import { cn } from "@/lib/utils";

const LIVE: ReadonlySet<Activity> = new Set(["recording", "listening", "speaking"]);

const RING: Record<Activity | "idle", string> = {
  connecting: "ring-rule",
  thinking: "ring-rule",
  ready: "ring-rule",
  recording: "ring-rule-strong",
  listening: "ring-rule-strong",
  speaking: "ring-ink-3",
  idle: "ring-rule"
};

function OrbIcon({ activity, pressable }: { activity: Activity | null; pressable: boolean }) {
  if (activity === null) return <MicOff className="h-7 w-7" aria-hidden />;
  if (activity === "connecting" || activity === "thinking") return <LoaderCircle className="h-7 w-7 motion-safe:animate-spin" aria-hidden />;
  if (activity === "speaking") return <AudioLines className="h-7 w-7" aria-hidden />;
  if (activity === "recording" && pressable) return <Send className="h-7 w-7 rtl:-scale-x-100" aria-hidden />;
  return <Mic className="h-7 w-7" aria-hidden />;
}

function useLevelScale(level: () => number, live: boolean) {
  const reduce = useAppReducedMotion();
  const raw = useMotionValue(0);
  const scale = useTransform(raw, [0, 1], [1, 1.28]);
  useEffect(() => {
    if (!live || reduce) {
      raw.set(0);
      return;
    }
    let frame = requestAnimationFrame(function tick() {
      raw.set(level());
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [level, live, raw, reduce]);
  return scale;
}

export function VoiceOrb({
  activity,
  level,
  label,
  onPress
}: {
  activity: Activity | null;
  level: () => number;
  label: string;
  onPress?: () => void;
}) {
  const scale = useLevelScale(level, activity !== null && LIVE.has(activity));
  const pressable = Boolean(onPress) && activity !== null;
  const core = cn(
    "relative grid h-24 w-24 place-items-center rounded-full ring-8 transition-colors duration-state",
    RING[activity ?? "idle"],
    activity === null ? "bg-sunk text-ink-3" : pressable && activity === "ready" ? "bg-indigo text-indigo-on hover:bg-indigo-hover" : "bg-sunk text-ink-1"
  );
  const halo = <motion.span aria-hidden style={{ scale }} className="absolute inset-0 rounded-full bg-ink-3/15" />;

  if (onPress && pressable) {
    return (
      <button type="button" onClick={onPress} aria-label={label} className={core} data-testid="voice-orb">
        {halo}
        <span className="relative">
          <OrbIcon activity={activity} pressable />
        </span>
      </button>
    );
  }
  return (
    <span className={core} data-testid="voice-orb">
      {halo}
      <span className="relative">
        <OrbIcon activity={activity} pressable={false} />
      </span>
    </span>
  );
}
