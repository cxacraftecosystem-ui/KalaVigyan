import { trackMark, type ListenMark, type TimedTrack } from "@/lib/listen";

export type ListenMarks = {
  subscribe: (onChange: () => void) => () => void;
  mark: () => ListenMark | null;
  time: () => number;
};

export type ListenMarkStore = ListenMarks & {
  follow: (track: TimedTrack | null, time: number) => void;
  show: (mark: ListenMark | null) => void;
};

export function sameMark(one: ListenMark | null, other: ListenMark | null): boolean {
  if (one === other) return true;
  if (one === null || other === null) return false;
  return one.sentenceId === other.sentenceId && one.wordIndex === other.wordIndex && one.words.length === other.words.length;
}

export function markOfSentence(marks: ListenMarks | null, sentenceId: string): ListenMark | null {
  const mark = marks?.mark() ?? null;
  return mark?.sentenceId === sentenceId ? mark : null;
}

export function listenMarkStore(first: ListenMark | null = null): ListenMarkStore {
  const listeners = new Set<() => void>();
  let mark = first;
  let time = 0;
  const changed = () => listeners.forEach((listener) => listener());
  return {
    subscribe: (onChange) => {
      listeners.add(onChange);
      return () => {
        listeners.delete(onChange);
      };
    },
    mark: () => mark,
    time: () => time,
    follow: (track, at) => {
      time = at;
      const next = trackMark(track, at);
      if (!sameMark(mark, next)) mark = next;
      changed();
    },
    show: (next) => {
      if (sameMark(mark, next)) return;
      mark = next;
      changed();
    }
  };
}
