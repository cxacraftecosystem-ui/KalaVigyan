"use client";

import Link from "next/link";

import { useAuth } from "@/components/AuthProvider";
import { ExplainerExport } from "@/components/learn/ExplainerExport";
import { ShareControl } from "@/components/learn/ShareControl";
import { buttonLook } from "@/components/ui/button";
import type { ExplainerRef } from "@/lib/explainerState";
import { newLessonHref } from "@/lib/lessonView";
import { canBuildLessons, canSaveExport } from "@/lib/permissions";
import { EXPLAINER_SHARE_PATH } from "@/lib/shareContract";

export function AnswerTools({ explainer }: { explainer: ExplainerRef }) {
  const user = useAuth().user;
  if (!canSaveExport(user)) return null;
  return (
    <>
      <ExplainerExport explainer={explainer} />
      <ShareControl sharePath={EXPLAINER_SHARE_PATH(explainer.explainerId, explainer.version)} kind="answer" />
      {canBuildLessons(user) ? (
        <Link href={newLessonHref(explainer)} {...buttonLook({ variant: "quiet", size: "sm" })} data-testid="make-lesson">
          Make a lesson
        </Link>
      ) : null}
    </>
  );
}
