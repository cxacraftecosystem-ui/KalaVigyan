"use client";

import { useState } from "react";

import { FormAlert } from "@/components/auth/FormAlert";
import { deleteConfirm, useConfirm } from "@/components/dialogs/ConfirmDialog";
import { failureMessage, useRemote } from "@/components/hooks/useRemote";
import { LessonList } from "@/components/learn/LessonList";
import { PageHeader } from "@/components/PageHeader";
import { LoadingPanel, RetryPanel } from "@/components/RemotePanels";
import { apiErrorMessage } from "@/lib/api";
import { deleteLesson, fetchLessons } from "@/lib/lessonApi";
import type { LessonSummary } from "@/lib/lessonContract";

const DELETE_FAILED = "Couldn't delete the lesson. Try again.";
const LESSONS_LINE = "Slides, a handout, a quiz and a reading list, each built from a saved answer and cited to its sources.";

export default function LessonsPage() {
  const lessons = useRemote(fetchLessons);
  const confirm = useConfirm();
  const [gone, setGone] = useState<ReadonlySet<string>>(() => new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(lesson: LessonSummary) {
    if (!(await confirm({ ...deleteConfirm(`Delete “${lesson.title}”?`, "Its slides and files go for good. The answer it was built from stays."), confirmLabel: "Delete lesson" }))) return;
    setBusy(lesson.id);
    setError(null);
    try {
      await deleteLesson(lesson.id);
      setGone((current) => new Set([...current, lesson.id]));
    } catch (cause) {
      setError(apiErrorMessage(cause, DELETE_FAILED));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader title="Lessons" description={LESSONS_LINE} back={false} />
      {error ? <FormAlert className="mb-4">{error}</FormAlert> : null}
      {lessons.failure ? (
        <RetryPanel message={failureMessage(lessons.failure, "Couldn't load your lessons.")} onRetry={lessons.retry} />
      ) : lessons.data ? (
        <LessonList lessons={lessons.data.items.filter((lesson) => !gone.has(lesson.id))} busy={busy} onDelete={(lesson) => void remove(lesson)} />
      ) : (
        <LoadingPanel label="Opening your lessons" />
      )}
    </>
  );
}
