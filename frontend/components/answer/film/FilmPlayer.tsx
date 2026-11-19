"use client";

import { useMemo, useRef, useState, type KeyboardEvent, type RefObject } from "react";

import { FilmButtons, FilmTiming } from "@/components/answer/film/FilmControls";
import { FilmScoreControls } from "@/components/answer/film/FilmScoreControls";
import { FilmSound } from "@/components/answer/film/FilmSound";
import { FilmCaption, FilmStage } from "@/components/answer/film/FilmStage";
import { useFilm, type Film } from "@/components/answer/film/useFilm";
import { useFilmScore } from "@/components/answer/film/useFilmScore";
import { FieldDialog } from "@/components/dialogs/FieldDialog";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { RetryLine } from "@/components/RemotePanels";
import { attributesForText, type AnswerLanguage } from "@/lib/answerLanguages";
import type { SectionView } from "@/lib/explainerState";
import { filmCaption, filmKey, filmMark } from "@/lib/filmScenes";
import { FULL_MIX, type FilmMix } from "@/lib/filmSound";

export type FilmPlayerProps = {
  answerId: string;
  question: string;
  language: AnswerLanguage;
  sections: readonly SectionView[];
  scoreOffered: boolean;
  onClose: () => void;
};

function keyHandler(film: Film, onMute: () => void) {
  return (event: KeyboardEvent<HTMLDivElement>) => {
    const target = event.target instanceof HTMLElement ? event.target.tagName : null;
    const action = filmKey(event.key, target);
    if (action === null || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    if (action === "mute") onMute();
    else film.send({ type: action });
  };
}

function FilmBody({ film, language, reduce }: { film: Film; language: AnswerLanguage; reduce: boolean }) {
  const { scene, clock } = film;
  const mark = useMemo(() => filmMark(scene, clock.time), [scene, clock.time]);
  if (film.load === "failed") return <RetryLine message={film.error ?? "Couldn't start the film. Try again."} onRetry={film.retry} />;
  if (!scene) return <div role="status" aria-label="Preparing the film" className="motion-pulse aspect-[16/9] w-full rounded-card bg-sunk" />;
  return (
    <>
      <FilmStage scene={scene} progress={film.progress} mark={mark} reduce={reduce} />
      <FilmCaption caption={filmCaption(scene, clock.time, language)} />
    </>
  );
}

export function FilmPlayerBody({ answerId, language, sections, scoreOffered, playRef }: Omit<FilmPlayerProps, "question" | "onClose"> & { playRef: RefObject<HTMLButtonElement | null> }) {
  const reduce = useAppReducedMotion();
  const film = useFilm(answerId, language.code, sections);
  const score = useFilmScore(answerId, language.code);
  const [mix, setMix] = useState<FilmMix>(FULL_MIX);
  const onMute = () => setMix((current) => ({ ...current, muted: !current.muted }));
  return (
    <div className="mt-4 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4" onKeyDown={keyHandler(film, onMute)} data-testid="film-player" data-motion={reduce ? "none" : "scenes"}>
      <FilmBody film={film} language={language} reduce={reduce} />
      <FilmTiming film={film} />
      <FilmButtons film={film} muted={mix.muted} onMute={onMute} playRef={playRef} />
      {scoreOffered ? <FilmScoreControls score={score} mix={mix} onMix={setMix} /> : null}
      <FilmSound film={film} score={scoreOffered ? score.score : null} mix={mix} onBroken={film.broken} />
    </div>
  );
}

export function FilmPlayer({ answerId, question, language, sections, scoreOffered, onClose }: FilmPlayerProps) {
  const playRef = useRef<HTMLButtonElement | null>(null);
  const title = attributesForText(question, language);
  return (
    <FieldDialog open onClose={onClose} title={<span {...title}>{question}</span>} className="max-w-5xl" initialFocusRef={playRef}>
      <FilmPlayerBody answerId={answerId} language={language} sections={sections} scoreOffered={scoreOffered} playRef={playRef} />
    </FieldDialog>
  );
}
