import type { ReactNode } from "react";

import { FactGrid, type Fact } from "@/components/editorial/FactGrid";
import { TextLink } from "@/components/ui/TextLink";
import { scriptOf } from "@/lib/answerLanguages";
import type { FieldTranscript, TranscriptLine, TranscriptSpeaker } from "@/lib/fieldVoicesContract";
import { formatClock, formatDate } from "@/lib/format";

const MACHINE_LABEL = "Machine translation";
const UNKNOWN_SPEAKER = "Speaker";
const NASTALIQ_LANGUAGES: ReadonlySet<string> = new Set(["ur", "ks"]);
const ROLE_LABEL: Record<NonNullable<TranscriptSpeaker["role"]>, string> = { ARTISAN: "artisan", DESIGNER: "designer", RESEARCHER: "researcher", OTHER: "speaker" };
const MEDIUM_LABEL: Record<FieldTranscript["mediaType"], string> = { AUDIO: "Sound recording", VIDEO: "Video recording" };

function speakerLabel(speakers: Map<string, TranscriptSpeaker>, line: TranscriptLine): string {
  return line.speakerKey ? (speakers.get(line.speakerKey)?.label ?? UNKNOWN_SPEAKER) : UNKNOWN_SPEAKER;
}

function speakerText(speaker: TranscriptSpeaker): string {
  return speaker.role ? `${speaker.label}, ${ROLE_LABEL[speaker.role]}` : speaker.label;
}

function scriptAttribute(text: string, language: string): string | undefined {
  const script = scriptOf(text);
  if (!script || script === "Latn") return undefined;
  return script === "Arab" && NASTALIQ_LANGUAGES.has(language.split("-")[0]) ? "Aran" : script;
}

function recordingFacts(transcript: FieldTranscript): Fact[] {
  const facts: (Fact | null)[] = [
    { label: "Recorded", value: formatDate(transcript.recordedAt) },
    transcript.durationMs !== null ? { label: "Length", value: <span className="lining-nums tabular-nums">{formatClock(Math.round(transcript.durationMs / 1000))}</span> } : null,
    { label: "Medium", value: MEDIUM_LABEL[transcript.mediaType] },
    { label: "Published by", value: transcript.publisher },
    transcript.workshop ? { label: "Workshop", value: transcript.workshop } : null,
    transcript.stage ? { label: "Stage", value: transcript.stage.label } : null,
    transcript.speakers.length > 0 ? { label: "Speakers", value: transcript.speakers.map(speakerText).join("; ") } : null,
    transcript.crafts.length > 0 ? { label: transcript.crafts.length === 1 ? "Craft" : "Crafts", value: <CraftLinks crafts={transcript.crafts} /> } : null
  ];
  return facts.filter((fact): fact is Fact => fact !== null);
}

function CraftLinks({ crafts }: { crafts: FieldTranscript["crafts"] }) {
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1">
      {crafts.map((craft) => (
        <TextLink key={craft.slug} href={craft.path}>
          {craft.name}
        </TextLink>
      ))}
    </span>
  );
}

function Part({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid min-w-0 gap-4">
      <h2 id={id} className="border-t border-ink-1 pt-4 font-reading text-h3 text-ink-1">
        {title}
      </h2>
      {children}
    </section>
  );
}

function TranscriptRow({ line, speaker }: { line: TranscriptLine; speaker: string }) {
  return (
    <li className="grid min-w-0 gap-1.5 border-b border-rule py-4">
      <p className="font-ui text-label text-ink-3">
        <span className="font-semibold text-ink-2">{speaker}</span> · <span className="lining-nums tabular-nums">{line.locator}</span>
      </p>
      <p lang={line.language} dir="auto" data-script={scriptAttribute(line.text, line.language)} className="max-w-measure font-reading text-body text-ink-1">
        {line.text}
      </p>
      {line.english && line.english !== line.text ? (
        <p lang="en" className="max-w-measure font-reading text-body-sm text-ink-2">
          {line.english}
          {line.englishSource === "MACHINE" ? <span className="ms-2 font-ui text-caption text-ink-3">{MACHINE_LABEL}</span> : null}
        </p>
      ) : null}
    </li>
  );
}

export function FieldTranscriptView({ transcript }: { transcript: FieldTranscript }) {
  const speakers = new Map(transcript.speakers.map((speaker) => [speaker.key, speaker]));
  return (
    <article className="grid min-w-0 gap-10">
      <Part id="recording-heading" title="About this recording">
        <FactGrid facts={recordingFacts(transcript)} />
        {transcript.context.length > 0 ? (
          <div className="grid max-w-measure gap-2 font-reading text-body-sm text-ink-2">
            {transcript.context.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        ) : null}
        <div className="grid max-w-measure gap-1">
          <p className="kicker">Cite this recording</p>
          <p className="font-reading text-body-sm text-ink-1 [overflow-wrap:anywhere]">{transcript.citation}</p>
        </div>
      </Part>
      <Part id="transcript-heading" title={`Transcript · ${transcript.lines.length} ${transcript.lines.length === 1 ? "line" : "lines"}`}>
        <ol className="grid min-w-0 border-t border-rule">
          {transcript.lines.map((line) => (
            <TranscriptRow key={line.id} line={line} speaker={speakerLabel(speakers, line)} />
          ))}
        </ol>
      </Part>
      {transcript.english ? (
        <Part id="english-heading" title="In English">
          <p lang="en" className="max-w-measure whitespace-pre-line font-reading text-body text-ink-1">
            {transcript.english}
          </p>
          {transcript.englishSource === "MACHINE" ? <p className="font-ui text-label text-ink-3">{MACHINE_LABEL}</p> : null}
        </Part>
      ) : null}
    </article>
  );
}
