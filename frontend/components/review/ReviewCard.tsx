"use client";

import { useState } from "react";

import { Field, TextArea } from "@/components/FormControls";
import { RecordNotice } from "@/components/records/RecordNotice";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import { Toggle } from "@/components/ui/Toggle";
import { apiErrorMessage } from "@/lib/api";
import { decideTestimony, testimonyNoteReady } from "@/lib/reviewQueueContract";
import { editItem, REJECT_REASON_LABELS, TESTIMONY_REJECT_REASONS, type RejectReason, type ReviewItem } from "@/lib/testimonyContract";

const REASON_OPTIONS = TESTIMONY_REJECT_REASONS.map((value) => ({ value, label: REJECT_REASON_LABELS[value] }));
const SCREEN_LABELS: Record<string, string> = { NAME_HELD_BACK: "Names someone the credit holds back. Edit it first." };

export function ReviewCard({ item, onDecided }: { item: ReviewItem; onDecided: () => void }) {
  const [current, setCurrent] = useState(item);
  const [claimText, setClaimText] = useState(item.claimText ?? "");
  const [english, setEnglish] = useState(item.english ?? "");
  const [checked, setChecked] = useState(item.englishSource !== "MACHINE");
  const [reason, setReason] = useState<RejectReason | "">("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const edited = claimText !== (current.claimText ?? "") || english !== (current.english ?? "");

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(apiErrorMessage(cause, "Couldn't save. Reload it."));
    } finally {
      setBusy(false);
    }
  }

  const saveEdit = () => run(async () => setCurrent(await editItem(current, { claimText, english })));
  const approve = () => run(async () => { await decideTestimony(current, { action: "approve", englishChecked: checked }); onDecided(); });
  const reject = () => run(async () => { if (reason) await decideTestimony(current, { action: "reject", reason, note }); onDecided(); });

  return (
    <li className="grid gap-4 border-t border-rule pt-5 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:gap-8" data-testid="review-card">
      <div className="grid content-start gap-2">
        <p className="kicker">
          {current.craft.name} · {current.speaker.district} · {current.locator}
        </p>
        <p className="font-ui text-ui font-normal text-ink-2">{current.line}</p>
        {current.context.before.text ? <p className="font-ui text-label text-ink-3">Asked: {current.context.before.english ?? current.context.before.text}</p> : null}
        {current.quote ? (
          <blockquote lang={current.language} dir={current.direction} className="font-reading text-quote italic text-ink-1">
            {current.quote}
          </blockquote>
        ) : null}
        {current.context.audio ? <audio controls preload="none" src={`${current.context.audio.url}#t=${current.context.audio.startMs / 1000},${current.context.audio.endMs / 1000}`} className="mt-1 w-full" /> : null}
      </div>
      <div className="grid content-start gap-4">
        <Field label="English">
          <TextArea value={english} onChange={(event) => setEnglish(event.target.value)} maxLength={600} rows={2} />
        </Field>
        <Field label="Fact">
          <TextArea value={claimText} onChange={(event) => setClaimText(event.target.value)} maxLength={300} rows={2} />
        </Field>
        {current.screens.map((screen) => (
          <RecordNotice key={screen} tone="error">
            {SCREEN_LABELS[screen] ?? screen}
          </RecordNotice>
        ))}
        <Toggle label="English checked" checked={checked} onChange={setChecked} disabled={busy} />
        {error ? <RecordNotice tone="error">{error}</RecordNotice> : null}
        <ActionGroup align="start">
          {edited ? (
            <Button type="button" variant="quiet" disabled={busy} onClick={() => void saveEdit()}>
              Save edit
            </Button>
          ) : null}
          <Button type="button" variant="primary" disabled={busy || edited || current.screens.length > 0} onClick={() => void approve()}>
            Approve
          </Button>
        </ActionGroup>
        <div className="grid gap-3 border-t border-rule pt-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] sm:items-end">
          <SearchableSelect value={reason} onChange={(next) => setReason(next as RejectReason)} options={REASON_OPTIONS} ariaLabel="Reason" placeholder="Reason" searchable={false} />
          <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} placeholder="Note for the artisan" aria-label="Note for the artisan" className="kv-input" />
          <Button type="button" variant="danger" data-danger disabled={busy || !testimonyNoteReady(reason, note)} onClick={() => void reject()}>
            Reject
          </Button>
        </div>
      </div>
    </li>
  );
}