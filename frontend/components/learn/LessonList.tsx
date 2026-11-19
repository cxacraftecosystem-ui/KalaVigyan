"use client";

import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { RowFacts } from "@/components/learn/RowFacts";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button, buttonLook } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import type { LessonSummary } from "@/lib/lessonContract";
import { lessonHref, slideCountText } from "@/lib/lessonView";
import { SAVED_PATH } from "@/lib/savedView";

export const LESSONS_EMPTY_TITLE = "Your lessons";
export const LESSONS_EMPTY_BODY = "Build a lesson from a saved answer. Its slides, handout, quiz and reading list wait here, each cited to its sources.";

function lessonFacts(lesson: LessonSummary) {
  return [
    ...(lesson.craft ? [{ label: "Craft", value: lesson.craft.name }] : []),
    { label: "Length", value: slideCountText(lesson.slideCount) },
    { label: "Version", value: lesson.version },
    { label: "Made", value: formatDate(lesson.createdAt) }
  ];
}

function LessonRow({ lesson, busy, onDelete }: { lesson: LessonSummary; busy: boolean; onDelete: (lesson: LessonSummary) => void }) {
  return (
    <li className="grid min-w-0 gap-3 border-b border-rule py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-6" data-testid="lesson-row">
      <div className="grid min-w-0 gap-1.5">
        <h2 className="min-w-0 font-ui text-h4 [overflow-wrap:anywhere]">
          <Link href={lessonHref(lesson.id)} className="kv-link font-semibold">
            {lesson.title}
          </Link>
        </h2>
        <RowFacts facts={lessonFacts(lesson)} />
      </div>
      <ActionGroup inline align="end">
        <Button type="button" variant="danger" size="sm" data-danger disabled={busy} busy={busy} busyLabel="Deleting" onClick={() => onDelete(lesson)} data-testid="lesson-delete">
          Delete<span className="sr-only"> {lesson.title}</span>
        </Button>
      </ActionGroup>
    </li>
  );
}

export function LessonList({ lessons, busy, onDelete }: { lessons: readonly LessonSummary[]; busy: string | null; onDelete: (lesson: LessonSummary) => void }) {
  if (lessons.length === 0) {
    return (
      <div data-testid="lessons-empty">
        <EmptyState
          title={LESSONS_EMPTY_TITLE}
          body={LESSONS_EMPTY_BODY}
          actions={
            <Link href={SAVED_PATH} {...buttonLook({ variant: "primary" })}>
              Open saved answers
            </Link>
          }
        />
      </div>
    );
  }
  return (
    <ul className="grid min-w-0 border-t border-ink-1" data-testid="lesson-list">
      {lessons.map((lesson) => (
        <LessonRow key={lesson.id} lesson={lesson} busy={busy === lesson.id} onDelete={onDelete} />
      ))}
    </ul>
  );
}
