import { apiFetch, buildQuery } from "@/lib/api";
import { languageCodeShape } from "@/lib/answerLanguages";
import { HTTPS_URL, UUID } from "@/lib/answerShapes";
import type { TextRange } from "@/lib/explainerView";
import { list, number, object, oneOf, optional, parseShape, ShapeError, text, type Shape } from "@/lib/shape";

export const LISTEN_VOICES = ["ELEVENLABS", "GEMINI"] as const;

export type ListenVoice = (typeof LISTEN_VOICES)[number];
export type ListenWord = { sentenceId: string; text: string; start: number; end: number };
export type ListenSentence = { sentenceId: string; start: number; end: number };
export type ListenTrack = { blockId: string; audioUrl: string; durationSeconds: number; words: ListenWord[]; sentences?: ListenSentence[] };
export type TimedTrack = Pick<ListenTrack, "words" | "sentences">;
export type ListenScript = { schemaVersion: 1; answerId: string; language: string; voice?: ListenVoice; tracks: ListenTrack[]; pending?: string[]; pollAfterSeconds?: number };
export type ListenOffer = { languages: string[]; voice?: ListenVoice };
export type ListenPosition = { track: number; time: number };
export type ListenMark = { sentenceId: string; words: ListenWord[]; wordIndex: number };
export type AfterTrack = "next" | "wait" | "end";

export const LISTEN_RATES = [1, 1.25, 1.5] as const;
export const LISTEN_POLLS_MAX = 100;
export const LISTEN_POLL_SECONDS = 3;

const listenWordShape: Shape<ListenWord> = object<ListenWord>({ sentenceId: text, text, start: number, end: number });
const listenSentenceShape: Shape<ListenSentence> = object<ListenSentence>({ sentenceId: text, start: number, end: number });
const listenVoiceShape = optional(oneOf(LISTEN_VOICES));

const listenScriptShape: Shape<ListenScript> = object<ListenScript>({
  schemaVersion: oneOf([1] as const),
  answerId: UUID,
  language: languageCodeShape,
  voice: listenVoiceShape,
  tracks: list(
    object<ListenTrack>({ blockId: text, audioUrl: HTTPS_URL, durationSeconds: number, words: list(listenWordShape), sentences: optional(list(listenSentenceShape)) }),
    1
  ),
  pending: optional(list(text)),
  pollAfterSeconds: optional(number)
});

const listenOfferShape = object<ListenOffer>({ languages: list(languageCodeShape), voice: listenVoiceShape });

export function listenPath(answerId: string, language: string, voice?: ListenVoice): string {
  return `/answers/${encodeURIComponent(answerId)}/listen${buildQuery({ language, voice })}`;
}

function checkTimings(timed: readonly { start: number; end: number }[], duration: number, path: string): void {
  let previous = 0;
  timed.forEach((entry, at) => {
    if (entry.start < previous || entry.end < entry.start || entry.start > duration) throw new ShapeError(`${path}[${at}]`, "a timing in reading order within the track");
    previous = entry.start;
  });
}

function checkTrack(track: ListenTrack, index: number): void {
  const path = `listen.tracks[${index}]`;
  const sentences = track.sentences ?? [];
  if (!(track.durationSeconds > 0)) throw new ShapeError(`${path}.durationSeconds`, "a positive length");
  if ((track.words.length > 0) === (sentences.length > 0)) throw new ShapeError(path, "a track timed by its words or by its sentences");
  if (track.words.some((word) => word.text === "")) throw new ShapeError(`${path}.words`, "words with their text");
  checkTimings(track.words, track.durationSeconds, `${path}.words`);
  checkTimings(sentences, track.durationSeconds, `${path}.sentences`);
}

function checkPending(script: ListenScript): void {
  const pending = script.pending ?? [];
  const read = new Set(script.tracks.map((track) => track.blockId));
  if (pending.some((blockId) => read.has(blockId)) || new Set(pending).size !== pending.length) throw new ShapeError("listen.pending", "blocks named once that have no track yet");
  const asks = script.pollAfterSeconds;
  if ((pending.length > 0) !== (asks !== undefined) || (asks !== undefined && !(asks > 0))) throw new ShapeError("listen.pollAfterSeconds", "a positive wait exactly while blocks are pending");
}

export function checkedScript(raw: unknown, answerId: string, language: string): ListenScript {
  const script = parseShape(listenScriptShape, raw);
  if (script.answerId !== answerId) throw new ShapeError("listen.answerId", `the answer ${answerId}`);
  if (script.language !== language) throw new ShapeError("listen.language", `the language ${language}`);
  script.tracks.forEach(checkTrack);
  checkPending(script);
  return script;
}

export async function fetchListenScript(answerId: string, language: string, voice?: ListenVoice): Promise<ListenScript> {
  return checkedScript(await apiFetch<unknown>(listenPath(answerId, language, voice)), answerId, language);
}

export function pendingBlocks(script: ListenScript | null): string[] {
  return script?.pending ?? [];
}

export function pollDelayMs(script: ListenScript): number {
  return (script.pollAfterSeconds ?? LISTEN_POLL_SECONDS) * 1000;
}

export function extendedScript(current: ListenScript, polled: ListenScript): ListenScript | null {
  if (polled.voice !== current.voice || polled.tracks.length < current.tracks.length) return null;
  if (current.tracks.some((track, at) => polled.tracks[at].blockId !== track.blockId)) return null;
  return { ...polled, tracks: [...current.tracks, ...polled.tracks.slice(current.tracks.length)] };
}

export function afterTrack(script: ListenScript | null, track: number): AfterTrack {
  if (script && track + 1 < script.tracks.length) return "next";
  return pendingBlocks(script).length > 0 ? "wait" : "end";
}

export function listenLanguagesOf(raw: unknown): string[] {
  if (raw === undefined || raw === null) return [];
  try {
    return parseShape(listenOfferShape, raw).languages;
  } catch (error) {
    if (!(error instanceof ShapeError)) throw error;
    console.error(new ShapeError(`answers/config listen.${error.path}`, error.expected));
    return [];
  }
}

export function scriptDuration(script: ListenScript): number {
  return script.tracks.reduce((sum, track) => sum + track.durationSeconds, 0);
}

export function elapsedOf(script: ListenScript, position: ListenPosition): number {
  const before = script.tracks.slice(0, position.track).reduce((sum, track) => sum + track.durationSeconds, 0);
  return before + Math.max(0, position.time);
}

export function activeIndex<T extends { start: number }>(timed: readonly T[], time: number): number {
  let low = 0;
  let high = timed.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (timed[middle].start <= time) {
      found = middle;
      low = middle + 1;
    } else high = middle - 1;
  }
  return found;
}

export function listenMark(script: ListenScript | null, position: ListenPosition): ListenMark | null {
  return trackMark(script?.tracks[position.track] ?? null, position.time);
}

function wordMark(words: readonly ListenWord[], time: number): ListenMark | null {
  const index = activeIndex(words, time);
  if (index < 0) return null;
  const sentenceId = words[index].sentenceId;
  const ofSentence = words.filter((word) => word.sentenceId === sentenceId);
  return { sentenceId, words: ofSentence, wordIndex: ofSentence.indexOf(words[index]) };
}

export function trackMark(track: TimedTrack | null, time: number): ListenMark | null {
  if (!track) return null;
  if (track.words.length > 0) return wordMark(track.words, time);
  const sentences = track.sentences ?? [];
  const index = activeIndex(sentences, time);
  return index < 0 ? null : { sentenceId: sentences[index].sentenceId, words: [], wordIndex: -1 };
}

export function firstSentenceId(track: TimedTrack): string | null {
  return track.words[0]?.sentenceId ?? track.sentences?.[0]?.sentenceId ?? null;
}

export function wordRanges(shown: string, words: readonly { text: string }[]): (TextRange | null)[] {
  let from = 0;
  return words.map((word) => {
    const at = shown.indexOf(word.text, from);
    if (at < 0) return null;
    from = at + word.text.length;
    return { from: at, to: from };
  });
}

export function nextRate(rate: number): number {
  const index = LISTEN_RATES.findIndex((option) => option === rate);
  return LISTEN_RATES[(index + 1) % LISTEN_RATES.length];
}
