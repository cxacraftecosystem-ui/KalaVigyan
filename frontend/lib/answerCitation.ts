import { citeKey, type Citable } from "@/lib/monographCite";
import { explainerHref } from "@/lib/savedView";

export type CitedAnswer = { explainerId: string; version: number; question: string };
export type ReaderPlace = { origin: string; path: string | null };

export function answerAddress(answer: Pick<CitedAnswer, "explainerId" | "version">, place: ReaderPlace): string {
  return `${place.origin.replace(/\/+$/, "")}${place.path ?? explainerHref(answer.explainerId, answer.version)}`;
}

export function answerCitable(answer: CitedAnswer, place: ReaderPlace): Citable {
  return { kind: "answer", title: answer.question.trim(), version: answer.version, url: answerAddress(answer, place), key: citeKey(`answer ${answer.explainerId.slice(0, 8)}`, answer.version) };
}
