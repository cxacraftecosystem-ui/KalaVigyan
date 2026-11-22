"use client";

import { useState } from "react";

import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { VoicePanel } from "@/components/voice/VoicePanel";
import { VOICE_BOARD_AVAILABILITY } from "@/lib/voiceBoard";

export function VoiceDockBoard() {
  const [open, setOpen] = useState(false);
  return (
    <section aria-label="The dock and its call" className="grid gap-4 py-10" data-testid="voice-dock-board">
      <p className="max-w-measure font-reading text-body text-ink-2">
        The dock a live call opens in: the notice to agree to, the orb that records and sends a turn, the transcript with its sources, and the end of the call. It talks to the voice routes of this site.
      </p>
      <ActionGroup align="start">
        <Button variant="quiet" onClick={() => setOpen(true)} disabled={open}>
          Open the voice dock
        </Button>
      </ActionGroup>
      <VoicePanel open={open} onClose={() => setOpen(false)} craftSlug={null} mode="VERIFIED" availability={VOICE_BOARD_AVAILABILITY} />
    </section>
  );
}
