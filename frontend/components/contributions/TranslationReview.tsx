"use client";

import { useState } from "react";

import { Field, TextInput } from "@/components/FormControls";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/Chip";
import { TextLink } from "@/components/ui/TextLink";
import { useTranslationReview } from "@/components/contributions/useTranslationReview";
import { DOCUMENT_LANGUAGE_CODES, LANGUAGE_NAMES, TEXT_SCRIPTS, textDirection } from "@/lib/documentLanguages";
import type { ReviewItem } from "@/lib/translationContract";

function WaitingItem({ item, busy, onDecide }: { item: ReviewItem; busy: boolean; onDecide: (approve: boolean, note: string | null) => void }) {
  const [note, setNote] = useState("");
  const name = LANGUAGE_NAMES[item.language];
  return (
    <li className="grid gap-2 border-t border-rule pt-3">
      <p className="kicker">
        {item.subject.slug} · {name.label}
        {item.current ? null : " · the English has changed since"}
      </p>
      <p lang="en" className="max-w-measure font-reading text-body-sm text-ink-2">
        {item.english}
      </p>
      <p lang={item.language} dir={textDirection(item.language)} data-script={TEXT_SCRIPTS[item.language]} className="max-w-measure font-reading text-body text-ink-1">
        {item.texts.join("")}
      </p>
      <Field label="Note to the translator" hint="Needed to reject; shown with the decision.">
        <TextInput value={note} disabled={busy} onChange={(event) => setNote(event.target.value)} />
      </Field>
      <ActionGroup align="start">
        <Button type="button" variant="quiet" size="sm" disabled={busy} onClick={() => onDecide(true, note.trim() || null)}>
          Approve
        </Button>
        <Button type="button" variant="danger" size="sm" data-danger="" disabled={busy || !note.trim()} onClick={() => onDecide(false, note.trim())}>
          Reject
        </Button>
      </ActionGroup>
      <TextLink href={item.pageUrl} external>
        Open the page in {name.label}
      </TextLink>
    </li>
  );
}

export function TranslationReview() {
  const review = useTranslationReview();
  return (
    <section className="grid gap-4" aria-labelledby="translation-review-h">
      <h2 id="translation-review-h" className="font-reading text-h3 text-ink-1">
        Review translations
      </h2>
      <p className="max-w-measure font-ui text-ui text-ink-2">Choose the languages you read; translations into them wait here for you, oldest first.</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Languages you read">
        {DOCUMENT_LANGUAGE_CODES.map((code) => (
          <Chip key={code} pressed={review.reads.includes(code)} disabled={review.busy} onClick={() => void review.toggle(code)}>
            <span lang={code} data-script={TEXT_SCRIPTS[code]} className="ui">
              {LANGUAGE_NAMES[code].autonym}
            </span>{" "}
            {LANGUAGE_NAMES[code].label}
          </Chip>
        ))}
      </div>
      {review.error ? (
        <p role="alert" className="font-ui text-ui text-error">
          {review.error}
        </p>
      ) : null}
      {review.list && review.list.items.length ? (
        <ul className="grid gap-4">
          {review.list.items.map((item) => (
            <WaitingItem key={item.id} item={item} busy={review.busy} onDecide={(approve, note) => void review.decide(item.id, approve, note)} />
          ))}
        </ul>
      ) : (
        <p className="font-ui text-label text-ink-3">Translations into the languages you choose appear here, each beside its English passage.</p>
      )}
    </section>
  );
}
