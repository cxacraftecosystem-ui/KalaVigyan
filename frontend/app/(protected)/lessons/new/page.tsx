"use client";

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { EmptyState } from "@/components/EmptyState";
import { failureMessage, useRemote } from "@/components/hooks/useRemote";
import { LessonBuilder } from "@/components/learn/LessonBuilder";
import { PageHeader } from "@/components/PageHeader";
import { LoadingPanel, RetryPanel } from "@/components/RemotePanels";
import { buttonLook } from "@/components/ui/button";
import { fetchExplainerDocument } from "@/lib/learningApi";
import { lessonHref } from "@/lib/lessonView";
import { EXPLAINER_PARAM, SAVED_PATH, VERSION_PARAM } from "@/lib/savedView";
import { positiveParam } from "@/lib/searchParams";

export default function NewLessonPage() {
  return (
    <Suspense fallback={null}>
      <NewLesson />
    </Suspense>
  );
}

function ChooseAnswer() {
  return (
    <EmptyState
      title="A lesson starts from an answer"
      body="Open a saved answer and choose Make a lesson. Its finished sections become slides, a handout and a quiz."
      actions={
        <Link href={SAVED_PATH} {...buttonLook({ variant: "primary" })}>
          Open saved answers
        </Link>
      }
    />
  );
}

function NewLesson() {
  const params = useSearchParams();
  const router = useRouter();
  const explainerId = params.get(EXPLAINER_PARAM);
  const version = positiveParam(params.get(VERSION_PARAM));
  const load = useMemo(() => (explainerId ? () => fetchExplainerDocument(explainerId, version) : null), [explainerId, version]);
  const document = useRemote(load);
  const header = <PageHeader title="Make a lesson" description={document.data?.explainer.question} />;

  if (!explainerId) {
    return (
      <>
        {header}
        <ChooseAnswer />
      </>
    );
  }
  return (
    <>
      {header}
      {document.failure ? (
        <RetryPanel message={failureMessage(document.failure, "Couldn't open that explainer.")} onRetry={document.retry} />
      ) : document.data ? (
        <LessonBuilder document={document.data} onBuilt={(pack) => router.replace(lessonHref(pack.id))} />
      ) : (
        <LoadingPanel label="Opening the answer" />
      )}
    </>
  );
}
