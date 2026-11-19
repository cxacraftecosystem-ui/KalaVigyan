"use client";

import { FormAlert } from "@/components/auth/FormAlert";
import { Markdown } from "@/components/Markdown";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate } from "@/lib/format";
import type { VoiceNotice } from "@/lib/voiceContract";

export function VoiceConsent({
  notice,
  busy,
  problem,
  onAccept,
  onDecline
}: {
  notice: VoiceNotice | null;
  busy: boolean;
  problem: string | null;
  onAccept: () => void;
  onDecline: () => void;
}) {
  if (!notice) return <Skeleton shape="lede" label="Opening the voice notice" />;
  return (
    <div className="grid gap-4" data-testid="voice-consent">
      <div className="grid gap-1">
        <h3 className="font-reading text-h3 text-ink-1">{notice.title}</h3>
        <p className="font-ui text-label text-ink-3 lining-nums tabular-nums">
          Version {notice.version}
          {notice.publishedAt ? ` · ${formatDate(notice.publishedAt)}` : ""}
        </p>
      </div>
      <div className="max-h-[40dvh] overflow-y-auto overscroll-contain rounded-control bg-sunk p-3">
        <Markdown text={notice.body} />
      </div>
      {problem ? <FormAlert>{problem}</FormAlert> : null}
      <ActionGroup>
        <Button type="button" variant="quiet" onClick={onDecline}>
          Not now
        </Button>
        <Button type="button" variant="primary" onClick={onAccept} busy={busy} busyLabel="Saving">
          Agree and start
        </Button>
      </ActionGroup>
    </div>
  );
}
