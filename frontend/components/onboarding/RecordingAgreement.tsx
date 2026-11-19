"use client";

import { useEffect, useState } from "react";

import { FormAlert } from "@/components/auth/FormAlert";
import { Markdown } from "@/components/Markdown";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/Skeleton";
import { apiErrorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { agreeToRecording, fetchRecordingNotice, type RecordingNotice } from "@/lib/profileContract";

function NoticeText({ notice }: { notice: RecordingNotice }) {
  return (
    <div lang={notice.language} className="grid max-h-80 gap-2 overflow-y-auto overscroll-contain rounded-control bg-sunk p-4">
      <h2 className="font-reading text-h3 text-ink-1">{notice.title}</h2>
      <p lang="en" className="font-ui text-label text-ink-3 lining-nums tabular-nums">
        Version {notice.version} · {formatDate(notice.publishedAt)}
      </p>
      <Markdown text={notice.body} />
    </div>
  );
}

export function RecordingAgreement({ language, onDone, notNow }: { language: string; onDone: () => void; notNow?: () => void }) {
  const [notice, setNotice] = useState<RecordingNotice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRecordingNotice(language)
      .then(setNotice)
      .catch((cause) => setError(apiErrorMessage(cause, "Couldn't load the recording notice. Try again.")));
  }, [language]);

  async function agree() {
    if (!notice) return;
    setBusy(true);
    setError(null);
    try {
      await agreeToRecording(notice.version, language);
      onDone();
    } catch (cause) {
      setError(apiErrorMessage(cause, "Couldn't save. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4" data-testid="recording-agreement">
      {notice ? <NoticeText notice={notice} /> : error ? null : <Skeleton shape="lede" label="Opening the recording notice" />}
      {error ? <FormAlert>{error}</FormAlert> : null}
      <ActionGroup>
        <Button type="button" variant="primary" disabled={!notice} busy={busy} busyLabel="Saving" onClick={() => void agree()}>
          I agree
        </Button>
        {notNow ? (
          <Button type="button" variant="quiet" disabled={busy} onClick={notNow}>
            Not now
          </Button>
        ) : null}
      </ActionGroup>
    </div>
  );
}
