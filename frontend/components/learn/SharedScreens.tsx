"use client";

import Link from "next/link";
import { useMemo } from "react";
import { MessageCircleQuestion } from "lucide-react";

import { CitedReading } from "@/components/answer/CitedReading";
import { ExplainerView } from "@/components/answer/ExplainerView";
import type { UnderstoodChange } from "@/components/answer/UnderstoodLine";
import { useAskHref } from "@/components/ask/useAskHref";
import { useRemote, type RemoteFailure } from "@/components/hooks/useRemote";
import { LessonPackView } from "@/components/learn/LessonPackView";
import { PageHeader } from "@/components/PageHeader";
import { RemoteView } from "@/components/RemotePanels";
import { buttonLook } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { languageFor, type AnswerLanguage } from "@/lib/answerLanguages";
import { listedSourceNumbers } from "@/lib/citations";
import { explainerStateOf } from "@/lib/explainerVersions";
import type { ExplainerVersionDocument } from "@/lib/learningContract";
import type { LessonPack } from "@/lib/lessonContract";
import { recordLoadFailure } from "@/lib/recordView";
import { fetchSharedAnswer, fetchSharedLesson, withReadingLanguages } from "@/lib/shareContract";

const NO_CHANGE: UnderstoodChange = { parts: new Set(), onChange: () => undefined };

function sharedFailure(noun: string): (failure: RemoteFailure) => string {
  return (failure) => {
    const cause = failure.cause;
    if (cause instanceof ApiError && (cause.status === 404 || cause.status === 422)) return `This ${noun} link no longer opens. Whoever shared it may have stopped sharing it.`;
    return cause instanceof ApiError ? recordLoadFailure(noun, cause.status, cause.message) : recordLoadFailure(noun, null);
  };
}

export function SharedAnswerScreen({ token }: { token: string }) {
  const load = useMemo(() => () => withReadingLanguages(fetchSharedAnswer(token)), [token]);
  const remote = useRemote(load);
  return (
    <div className="grid min-w-0 gap-4" data-testid="shared-answer">
      <RemoteView remote={remote} failed={sharedFailure("answer")}>
        {(shared) => <SharedAnswer document={shared.body} languages={shared.languages} />}
      </RemoteView>
    </div>
  );
}

function SharedAnswer({ document, languages }: { document: ExplainerVersionDocument; languages: AnswerLanguage[] }) {
  const state = useMemo(() => explainerStateOf(document), [document]);
  const askHref = useAskHref({ craft: document.explainer.understood.crafts[0]?.slug ?? null });
  const ask = (
    <Link href={askHref} {...buttonLook({ variant: "quiet", size: "sm" })} data-testid="shared-ask">
      <MessageCircleQuestion aria-hidden />
      Ask your own question
    </Link>
  );
  return (
    <ExplainerView
      state={state}
      streaming={false}
      languages={languages}
      depthLabel={null}
      change={NO_CHANGE}
      listenLanguages={[]}
      onFollowUp={null}
      onFreshResearch={null}
      tools={ask}
    />
  );
}

export function SharedLessonScreen({ token }: { token: string }) {
  const load = useMemo(() => () => withReadingLanguages(fetchSharedLesson(token)), [token]);
  const remote = useRemote(load);
  return (
    <div data-testid="shared-lesson">
      <PageHeader title={remote.data?.body.title ?? "Shared lesson"} />
      <RemoteView remote={remote} failed={sharedFailure("lesson")}>
        {(shared) => <SharedLesson pack={shared.body} languages={shared.languages} />}
      </RemoteView>
    </div>
  );
}

function SharedLesson({ pack, languages }: { pack: LessonPack; languages: AnswerLanguage[] }) {
  const numbers = useMemo(() => listedSourceNumbers(pack.sources), [pack]);
  return (
    <CitedReading sources={pack.sources} numbers={numbers} language={languageFor(pack.language, languages)}>
      <LessonPackView pack={pack} />
    </CitedReading>
  );
}
