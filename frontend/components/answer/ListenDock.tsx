"use client";

import { useSyncExternalStore } from "react";
import { CircleAlert, Pause, Play, X } from "lucide-react";

import { ListenAudio } from "@/components/answer/ListenAudio";
import type { Listen } from "@/components/answer/useListen";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/IconButton";
import { ProgressBar } from "@/components/ui/ProgressBar";
import type { AnswerLanguage } from "@/lib/answerLanguages";
import { formatClock } from "@/lib/format";
import { elapsedOf, scriptDuration } from "@/lib/listen";

const PLAY_BUTTON = "grid h-12 w-12 shrink-0 place-items-center rounded-full bg-indigo text-indigo-on transition-colors duration-state hover:bg-indigo-hover aria-disabled:cursor-wait aria-disabled:bg-sunk aria-disabled:text-ink-3";
const DOCK_PLACE = { bottom: "calc(var(--bottom-nav-h, 0px) + 0.75rem)" };

function Timing({ listen }: { listen: Listen }) {
  const time = useSyncExternalStore(listen.marks.subscribe, listen.marks.time, listen.marks.time);
  if (!listen.script) return null;
  const total = scriptDuration(listen.script);
  const elapsed = Math.min(total, elapsedOf(listen.script, { track: listen.track, time }));
  const percent = total > 0 ? Math.round((elapsed / total) * 100) : 0;
  return (
    <div className="grid min-w-0 flex-1 gap-1.5">
      <ProgressBar percent={percent} role="progressbar" aria-label="Played" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} className="h-1.5" />
      <span className="font-ui text-caption tabular-nums text-ink-3">
        {formatClock(elapsed)} of {formatClock(total)}
      </span>
    </div>
  );
}

const PREPARING: Partial<Record<Listen["status"], string>> = { loading: "Preparing the audio…", waiting: "Preparing the next part…" };

function Player({ listen }: { listen: Listen }) {
  const playing = listen.status === "playing";
  const preparing = PREPARING[listen.status];
  return (
    <div className="flex items-center gap-3">
      <button type="button" className={PLAY_BUTTON} aria-label={playing ? "Pause" : "Play"} aria-disabled={preparing !== undefined || undefined} onClick={listen.toggle}>
        {preparing ? <span className="kv-spin" aria-hidden /> : playing ? <Pause className="h-5 w-5" aria-hidden /> : <Play className="h-5 w-5" aria-hidden />}
      </button>
      <span role="status" className={preparing ? "flex-1 font-ui text-ui text-ink-3" : "sr-only"}>
        {preparing}
      </span>
      {preparing ? null : <Timing listen={listen} />}
      <Button variant="quiet" size="sm" aria-label={`Speed ${listen.rate} times`} onClick={listen.cycleRate}>
        {listen.rate}×
      </Button>
    </div>
  );
}

export function ListenDock({ listen, language }: { listen: Listen; language: AnswerLanguage }) {
  if (listen.status === "idle") return null;
  const track = listen.script?.tracks[listen.track] ?? null;
  return (
    <aside
      aria-label="Listen"
      style={DOCK_PLACE}
      className="fixed inset-x-3 z-sticky grid gap-2 rounded-card border border-rule bg-raised p-3 shadow-pop sm:start-auto sm:end-6 sm:w-[26rem]"
      data-testid="listen-dock"
      data-status={listen.status}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-ui text-label text-ink-2" lang={language.code}>
          Listen · {language.autonym}
        </span>
        <IconButton label="Stop listening" icon={<X />} onClick={listen.stop} />
      </div>
      {listen.status === "failed" ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 font-ui text-ui text-ink-1">
          <CircleAlert className="h-4 w-4 shrink-0 text-error" aria-hidden />
          <span className="min-w-0 flex-1">{listen.error}</span>
          <Button variant="quiet" size="sm" onClick={listen.start}>
            Try again
          </Button>
        </div>
      ) : (
        <Player listen={listen} />
      )}
      {track ? (
        <ListenAudio
          key={listen.track}
          src={track.audioUrl}
          playing={listen.status === "playing"}
          rate={listen.rate}
          onTime={listen.onTime}
          onEnded={listen.onEnded}
          onBroken={listen.onBroken}
          onRefused={listen.onRefused}
        />
      ) : null}
    </aside>
  );
}
