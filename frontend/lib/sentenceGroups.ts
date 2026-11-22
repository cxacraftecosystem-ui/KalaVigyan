import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import { listText, lowerFirst, upperFirst } from "@/lib/format";
import type { AnswerSentence } from "@/lib/types";

export type SentenceGroup<T> = { key: string; sentence: ExplainerSentence; items: T[] };
export type Sayer = (sentence: ExplainerSentence | null | undefined) => ExplainerSentence | null;

type Joined = { keys: Set<string>; indices: number[] };

const WORD = /[\p{L}\p{M}\p{N}]+/gu;

export function sentenceKey(sentence: Pick<AnswerSentence, "text" | "original">): string {
  return sentence.original ?? sentence.text;
}

export function bySentence<T>(items: readonly T[], sentenceOf: (item: T) => ExplainerSentence): SentenceGroup<T>[] {
  const groups = new Map<string, SentenceGroup<T>>();
  for (const item of items) {
    const sentence = sentenceOf(item);
    const key = sentenceKey(sentence);
    const group = groups.get(key) ?? { key, sentence, items: [] };
    group.items.push(item);
    groups.set(key, group);
  }
  return [...groups.values()];
}

export function joinedBy<T>(items: readonly T[], keysOf: (item: T) => readonly string[]): T[][] {
  let groups: Joined[] = [];
  items.forEach((item, index) => {
    const keys = keysOf(item);
    const meets = (group: Joined) => keys.some((key) => group.keys.has(key));
    const joined: Joined = { keys: new Set(keys), indices: [index] };
    for (const group of groups.filter(meets)) {
      group.keys.forEach((key) => joined.keys.add(key));
      joined.indices.push(...group.indices);
    }
    const at = groups.findIndex(meets);
    groups = groups.filter((group) => !meets(group));
    groups.splice(at === -1 ? groups.length : at, 0, joined);
  });
  return groups.map((group) => [...group.indices].sort((a, b) => a - b).map((index) => items[index]));
}

export function onceSaid(): Sayer {
  const said = new Set<string>();
  return (sentence) => {
    if (!sentence || said.has(sentenceKey(sentence))) return null;
    said.add(sentenceKey(sentence));
    return sentence;
  };
}

export function onceEach(sentences: readonly ExplainerSentence[]): ExplainerSentence[] {
  const say = onceSaid();
  return sentences.flatMap((sentence) => say(sentence) ?? []);
}

export function sentenceWords(sentences: readonly ExplainerSentence[]): Set<string> {
  return new Set(sentences.flatMap((sentence) => sentenceKey(sentence).match(WORD) ?? []));
}

function laterName(name: string, words: ReadonlySet<string>): string {
  const first = name.match(WORD)?.[0] ?? "";
  return words.has(lowerFirst(first)) ? lowerFirst(name) : name;
}

export function namesText(names: readonly string[], words: ReadonlySet<string>): string {
  return listText(names.map((name, index) => (index === 0 ? upperFirst(name) : laterName(name, words))));
}
