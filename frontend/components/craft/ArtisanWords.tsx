"use client";

import { useId } from "react";

import { FieldListMore } from "@/components/craft/FieldListMore";
import { useFieldList } from "@/components/craft/useFieldList";
import { TextLink } from "@/components/ui/TextLink";
import type { FieldVoicesList, PageVoice } from "@/lib/fieldVoicesContract";
import { FIRST_QUOTES, FULL_INTERVIEW, interviewPath, MACHINE_TRANSLATION, quotesOf, VOICES_HEADING, voiceScript } from "@/lib/fieldVoicesView";
import { cn } from "@/lib/utils";

const QUOTES_NOUN = "quotes";

function Spoken({ voice }: { voice: PageVoice }) {
  const script = voiceScript(voice.quote, voice.language);
  return (
    <p lang={voice.language} dir="auto" data-script={script} className={cn("font-reading text-quote text-ink-1", script ? null : "italic")}>
      “{voice.quote}”
    </p>
  );
}

function English({ voice }: { voice: PageVoice }) {
  if (!voice.english || voice.english === voice.quote) return null;
  return (
    <p lang="en" className="font-reading text-body-sm text-ink-2">
      {voice.english}
      {voice.englishSource === "MACHINE" ? <span className="ms-2 font-ui text-caption text-ink-3">{MACHINE_TRANSLATION}</span> : null}
    </p>
  );
}

function VoiceItem({ voice }: { voice: PageVoice }) {
  return (
    <li className="min-w-0 border-b border-rule py-5" data-testid="field-voice" data-origin={voice.origin}>
      <figure className="grid max-w-measure gap-2">
        <blockquote className="grid gap-1.5">
          <Spoken voice={voice} />
          <English voice={voice} />
        </blockquote>
        <figcaption className="grid gap-1 font-ui text-label text-ink-3">
          <span className="[overflow-wrap:anywhere]">{voice.citation}</span>
          {voice.recordingId ? (
            <span>
              <TextLink href={interviewPath(voice.recordingId)} standalone>
                {FULL_INTERVIEW}
              </TextLink>
            </span>
          ) : null}
        </figcaption>
      </figure>
    </li>
  );
}

export function ArtisanWords({ first }: { first: FieldVoicesList }) {
  const list = useFieldList(first, quotesOf, FIRST_QUOTES);
  const headingId = useId();
  const listId = useId();
  if (list.total === 0) return null;
  return (
    <section aria-labelledby={headingId} className="grid min-w-0 gap-2 border-t border-ink-1 pt-4" data-testid="artisan-words">
      <h2 id={headingId} className="font-reading text-h3 text-ink-1">
        {VOICES_HEADING}
      </h2>
      <ul id={listId} className="grid min-w-0">
        {list.shown.map((voice) => (
          <VoiceItem key={voice.itemId} voice={voice} />
        ))}
      </ul>
      <FieldListMore list={list} noun={QUOTES_NOUN} controls={listId} />
    </section>
  );
}
