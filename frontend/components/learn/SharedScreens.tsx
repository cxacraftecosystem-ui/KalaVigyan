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
import { ENGLISH, languageFor } from "@/lib/answerLanguages";
import { listedSourceNumbers } from "@/lib/citations";
import { explainerStateOf } from "@/lib/explainerVersions";
import type { ExplainerVersionDocument } from "@/lib/learningContract";
import type { LessonPack } from "@/lib/lessonContract";
import { recordLoadFailure } from "@/lib/recordView";
import { fetchSharedAnswer, fetchSharedLesson } from "@/lib/shareContract";

const READING_LANGUAGES = [ENGLISH];
const NO_CHANGE: UnderstoodChange = { parts: new Set(), onChange: () => undefined };

function sharedFailure(noun: string): (failure: RemoteFailure) => string {
  return (failure) => {
    const cause = failure.cause;
    if (cause instanceof ApiError && (cause.status === 404 || cause.status === 422)) return `This ${noun} link no longer opens. Whoever shared it may have stopped sharing it.`;
    return cause instanceof ApiError ? recordLoadFailure(noun, cause.status, cause.message) : recordLoadFailure(noun, null);
  };
}

export function SharedAnswerScreen({ token }: { token: string }) {
  const load = useMemo(() => () => fetchSharedAnswer(token), [token]);
  const remote = useRemote(load);
  return (
    <div className="grid min-w-0 gap-4" data-testid="shared-answer">
      <RemoteView remote={remote} failed={sharedFailure("answer")}>
        {(document) => <SharedAnswer document={document} />}
      </RemoteView>
    </div>
  );
}

function SharedAnswer({ document }: { document: ExplainerVersionDocument }) {
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
      languages={READING_LANGUAGES}
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
  const load = useMemo(() => () => fetchSharedLesson(token), [token]);
  const remote = useRemote(load);
  return (
    <div data-testid="shared-lesson">
      <PageHeader title={remote.data?.title ?? "Shared lesson"} />
      <RemoteView remote={remote} failed={sharedFailure("lesson")}>
        {(pack) => <SharedLesson pack={pack} />}
      </RemoteView>
    </div>
  );
}

function SharedLesson({ pack }: { pack: LessonPack }) {
  const numbers = useMemo(() => listedSourceNumbers(pack.sources), [pack]);
  return (
    <CitedReading sources={pack.sources} numbers={numbers} language={languageFor(pack.language, READING_LANGUAGES)}>
      <LessonPackView pack={pack} />
    </CitedReading>
  );
}
