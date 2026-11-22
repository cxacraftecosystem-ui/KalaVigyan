import { apiFetch, buildQuery } from "@/lib/api";
import { languageCodeShape } from "@/lib/answerLanguages";
import { HTTPS_URL, INSTANT, UUID } from "@/lib/answerShapes";
import { BLOCK_ID } from "@/lib/explainerBlockBase";
import { boolean, integer, list, matching, nullable, number, object, oneOf, parseShape, ShapeError, text, type Shape } from "@/lib/shape";

export const SCORE_LABEL = "AI music and sound";
export const SCORE_ASKS_MAX = 60;
export const SCORE_TOOK_TOO_LONG = "The music took too long to make.";

export type ScoreMusic = { audioUrl: string; durationSeconds: number; model: string };
export type ScoreCue = { blockId: string; offsetSeconds: number; audioUrl: string; durationSeconds: number; model: string };
export type ScoreLabel = { text: typeof SCORE_LABEL; models: string[]; generatedOn: string };
export type FilmScore = {
  schemaVersion: 1;
  answerId: string;
  language: string;
  music: ScoreMusic | null;
  cues: ScoreCue[];
  label: ScoreLabel;
  urlExpiresAt: string;
};
export type FilmOffer = { score: boolean };
export type FilmScoreMaking = { answerId: string; language: string; pollAfterSeconds: number };
export type ScoreWait = (seconds: number, signal?: AbortSignal) => Promise<void>;

const filmScoreShape: Shape<FilmScore> = object<FilmScore>({
  schemaVersion: oneOf([1] as const),
  answerId: UUID,
  language: languageCodeShape,
  music: nullable(object<ScoreMusic>({ audioUrl: HTTPS_URL, durationSeconds: number, model: text })),
  cues: list(object<ScoreCue>({ blockId: BLOCK_ID, offsetSeconds: number, audioUrl: HTTPS_URL, durationSeconds: number, model: text })),
  label: object<ScoreLabel>({
    text: oneOf([SCORE_LABEL] as const),
    models: list(text, 1),
    generatedOn: matching(/^\d{4}-\d{2}-\d{2}$/, "a calendar day")
  }),
  urlExpiresAt: INSTANT
});

const filmScoreMakingShape: Shape<FilmScoreMaking> = object<FilmScoreMaking>({
  answerId: UUID,
  language: languageCodeShape,
  pollAfterSeconds: integer
});

export const filmOfferShape: Shape<FilmOffer> = object<FilmOffer>({ score: boolean });

export function filmScoreOffered(raw: unknown): boolean {
  if (raw === undefined || raw === null) return false;
  try {
    return parseShape(filmOfferShape, raw).score;
  } catch (error) {
    if (!(error instanceof ShapeError)) throw error;
    console.error(new ShapeError(`answers/config film.${error.path}`, error.expected));
    return false;
  }
}

export async function fetchFilmScore(answerId: string, language: string, options: { signal?: AbortSignal; wait?: ScoreWait } = {}): Promise<FilmScore> {
  const wait = options.wait ?? waitSeconds;
  for (let ask = 0; ask < SCORE_ASKS_MAX; ask += 1) {
    const raw = await apiFetch<unknown>(filmScorePath(answerId, language), { signal: options.signal });
    const making = scoreMaking(raw, answerId, language);
    if (making === null) return checkedFilmScore(raw, answerId, language);
    await wait(making.pollAfterSeconds, options.signal);
  }
  throw new Error(SCORE_TOOK_TOO_LONG);
}

export function scoreMaking(raw: unknown, answerId: string, language: string): FilmScoreMaking | null {
  if (typeof raw !== "object" || raw === null || !("pollAfterSeconds" in raw)) return null;
  const making = parseShape(filmScoreMakingShape, raw);
  if (making.answerId !== answerId || making.language !== language) throw new ShapeError("score", `the score of ${answerId} in ${language}`);
  if (making.pollAfterSeconds < 1) throw new ShapeError("score.pollAfterSeconds", "a wait of a second or more");
  return making;
}

function waitSeconds(seconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, seconds * 1000);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(signal.reason);
    }, { once: true });
  });
}

export function filmScorePath(answerId: string, language: string): string {
  return `/answers/${encodeURIComponent(answerId)}/film-score${buildQuery({ language })}`;
}

export function checkedFilmScore(raw: unknown, answerId: string, language: string): FilmScore {
  const score = parseShape(filmScoreShape, raw);
  if (score.answerId !== answerId) throw new ShapeError("score.answerId", `the answer ${answerId}`);
  if (score.language !== language) throw new ShapeError("score.language", `the language ${language}`);
  if (score.music === null && score.cues.length === 0) throw new ShapeError("score", "music or a cue");
  const scenes = score.cues.map((cue) => cue.blockId);
  if (new Set(scenes).size !== scenes.length) throw new ShapeError("score.cues", "one cue per scene at most");
  if (score.cues.some((cue) => cue.offsetSeconds < 0 || !(cue.durationSeconds > 0))) {
    throw new ShapeError("score.cues", "cues placed at or after their scene's start");
  }
  return score;
}
