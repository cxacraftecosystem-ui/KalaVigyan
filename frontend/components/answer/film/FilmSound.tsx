"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

import type { Film } from "@/components/answer/film/useFilm";
import { ListenAudio } from "@/components/answer/ListenAudio";
import type { FilmScore, ScoreCue, ScoreMusic } from "@/lib/filmScore";
import { sceneTrack } from "@/lib/filmScenes";
import { applyLevel, bedDrifted, bedTime, cueDue, filmLevels, sceneCue, volumeIsFixed, type FilmMix, type SoundLevel } from "@/lib/filmSound";

type FilmGain = { routed: boolean; connect: (audio: HTMLAudioElement) => GainNode | null };

function ignoreRefusedPlay(): void {}

function useFilmGain(): FilmGain {
  const context = useRef<AudioContext | null>(null);
  const [routed] = useState(() => typeof Audio !== "undefined" && typeof AudioContext !== "undefined" && volumeIsFixed(new Audio()));
  useEffect(() => {
    if (!routed) return;
    const unlock = () => {
      context.current ??= new AudioContext();
      context.current.resume().catch(ignoreRefusedPlay);
    };
    document.addEventListener("pointerdown", unlock, true);
    document.addEventListener("keydown", unlock, true);
    return () => {
      document.removeEventListener("pointerdown", unlock, true);
      document.removeEventListener("keydown", unlock, true);
      context.current?.close().catch(ignoreRefusedPlay);
      context.current = null;
    };
  }, [routed]);
  const connect = useCallback((audio: HTMLAudioElement): GainNode | null => {
    const sound = context.current;
    if (!sound) return null;
    const gain = sound.createGain();
    sound.createMediaElementSource(audio).connect(gain).connect(sound.destination);
    return gain;
  }, []);
  return { routed, connect };
}

function useGainOf(ref: RefObject<HTMLAudioElement | null>, gain: FilmGain): RefObject<GainNode | null> {
  const node = useRef<GainNode | null>(null);
  useEffect(() => {
    const audio = ref.current;
    if (audio && gain.routed && node.current === null) node.current = gain.connect(audio);
  });
  return node;
}

function MusicBed({ music, playing, level, elapsed, gain }: { music: ScoreMusic; playing: boolean; level: SoundLevel; elapsed: number; gain: FilmGain }) {
  const ref = useRef<HTMLAudioElement | null>(null);
  const node = useGainOf(ref, gain);
  const { volume, muted } = level;
  useEffect(() => {
    const audio = ref.current;
    if (!audio) return;
    applyLevel(audio, { volume, muted }, node.current);
    if (bedDrifted(audio.currentTime, elapsed, music.durationSeconds)) audio.currentTime = bedTime(elapsed, music.durationSeconds);
    if (playing && audio.paused) audio.play().catch(ignoreRefusedPlay);
    if (!playing && !audio.paused) audio.pause();
  }, [playing, volume, muted, elapsed, music.durationSeconds, node]);
  return <audio ref={ref} src={music.audioUrl} loop preload="auto" crossOrigin={gain.routed ? "anonymous" : undefined} className="hidden" data-testid="film-music" />;
}

function SceneCue({ cue, time, playing, level, gain }: { cue: ScoreCue; time: number; playing: boolean; level: SoundLevel; gain: FilmGain }) {
  const ref = useRef<HTMLAudioElement | null>(null);
  const node = useGainOf(ref, gain);
  const fired = useRef(false);
  const { volume, muted } = level;
  useEffect(() => {
    const audio = ref.current;
    if (!audio) return;
    applyLevel(audio, { volume, muted }, node.current);
    if (!playing) {
      if (!audio.paused) audio.pause();
      return;
    }
    const resumes = fired.current && audio.paused && !audio.ended && audio.currentTime > 0;
    if ((!fired.current && cueDue(cue, time)) || resumes) {
      fired.current = true;
      audio.play().catch(ignoreRefusedPlay);
    }
  }, [cue, time, playing, volume, muted, node]);
  return <audio ref={ref} src={cue.audioUrl} preload="auto" crossOrigin={gain.routed ? "anonymous" : undefined} className="hidden" data-testid="film-cue" />;
}

export function FilmSound({ film, score, mix, onBroken }: { film: Film; score: FilmScore | null; mix: FilmMix; onBroken: () => void }) {
  const { clock, scene, send } = film;
  const playing = film.load === "ready" && clock.playing && !clock.ended;
  const current = scene ? sceneTrack(scene, clock.time) : null;
  const cue = scene ? sceneCue(score, scene.block.id) : null;
  const onRefused = useCallback(() => send({ type: "pause" }), [send]);
  const levels = filmLevels(mix, film.elapsed, film.total);
  const gain = useFilmGain();
  return (
    <>
      {current && film.load === "ready" ? (
        <ListenAudio
          key={`${clock.scene}:${clock.take}:${current.at}`}
          src={current.track.audioUrl}
          playing={playing}
          rate={1}
          muted={mix.muted}
          onTime={(time) => send({ type: "heard", scene: clock.scene, time: current.start + time })}
          onEnded={() => send({ type: "trackEnded", scene: clock.scene, time: current.start + current.track.durationSeconds })}
          onBroken={onBroken}
          onRefused={onRefused}
        />
      ) : null}
      {score?.music ? <MusicBed music={score.music} playing={playing} level={levels.bed} elapsed={film.elapsed} gain={gain} /> : null}
      {cue ? <SceneCue key={`${clock.scene}:${clock.take}`} cue={cue} time={clock.time} playing={playing} level={levels.cue} gain={gain} /> : null}
    </>
  );
}
