"use client";

import { PhoneOff, RotateCw } from "lucide-react";

import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import type { VoicePhase } from "@/lib/voiceCall";

export function VoiceControls({
  phase,
  onEnd,
  onAgain,
  onClose
}: {
  phase: VoicePhase;
  onEnd: () => void;
  onAgain: () => void;
  onClose: () => void;
}) {
  if (phase === "starting" || phase === "live") {
    return (
      <ActionGroup fill>
        <Button type="button" variant="primary" onClick={onEnd} data-testid="voice-end">
          <PhoneOff aria-hidden />
          End
        </Button>
      </ActionGroup>
    );
  }
  if (phase === "ended" || phase === "failed") {
    return (
      <ActionGroup>
        <Button type="button" variant="quiet" onClick={onClose}>
          Close
        </Button>
        <Button type="button" variant="primary" onClick={onAgain}>
          <RotateCw aria-hidden />
          {phase === "failed" ? "Try again" : "Talk again"}
        </Button>
      </ActionGroup>
    );
  }
  return null;
}
