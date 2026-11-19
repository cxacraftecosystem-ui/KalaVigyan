"use client";

import Link from "next/link";
import { Presentation } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { FieldBlock } from "@/components/FormControls";
import { ExplainerExport } from "@/components/learn/ExplainerExport";
import { SaveButton } from "@/components/learn/SaveButton";
import { ShareControl } from "@/components/learn/ShareControl";
import { buttonLook } from "@/components/ui/button";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import type { ExplainerRef, SectionView } from "@/lib/explainerState";
import { versionChanges, versionOptions } from "@/lib/explainerVersions";
import type { VersionMark } from "@/lib/learningContract";
import { newLessonHref } from "@/lib/lessonView";
import { canBuildLessons, canSaveExport } from "@/lib/permissions";
import { EXPLAINER_SHARE_PATH } from "@/lib/shareContract";
import type { User } from "@/lib/types";

export type VersionChoice = { versions: VersionMark[]; viewing: VersionMark | null; onPick: (version: number) => void };

export function ExplainerTools({ explainer }: { explainer: ExplainerRef }) {
  return <ExplainerActions explainer={explainer} user={useAuth().user} />;
}

export function ExplainerActions({ explainer, user }: { explainer: ExplainerRef; user: User | null }) {
  if (!canSaveExport(user)) return null;
  return (
    <>
      <SaveButton explainerId={explainer.explainerId} />
      <ExplainerExport explainer={explainer} />
      <ShareControl sharePath={EXPLAINER_SHARE_PATH(explainer.explainerId, explainer.version)} kind="answer" />
      {canBuildLessons(user) ? (
        <Link href={newLessonHref(explainer)} {...buttonLook({ variant: "quiet", size: "sm" })} data-testid="make-lesson">
          <Presentation aria-hidden />
          Make a lesson
        </Link>
      ) : null}
    </>
  );
}

export function VersionPicker({ choice, sections }: { choice: VersionChoice; sections: readonly SectionView[] }) {
  const { versions, viewing, onPick } = choice;
  if (versions.length < 2 || !viewing) return null;
  const latest = versions[versions.length - 1].version;
  const changes = versionChanges(viewing, sections);
  return (
    <section className="grid min-w-0 gap-3 border-y border-rule py-4 sm:grid-cols-[minmax(0,18rem)_minmax(0,1fr)] sm:items-end sm:gap-6" data-testid="version-picker">
      <FieldBlock label="Version">
        <SearchableSelect value={String(viewing.version)} options={versionOptions(versions)} onChange={(next) => onPick(Number(next))} searchable advanceOnSelect={false} />
      </FieldBlock>
      <div className="grid min-w-0 justify-items-start gap-1.5 font-ui text-ui">
        {changes.length > 0 ? (
          <p className="font-normal text-ink-2" data-testid="version-changes">
            {changes.join(" · ")}
          </p>
        ) : null}
        {viewing.version < latest ? (
          <button type="button" className="kv-link pointer-coarse:min-h-11" data-standalone="" onClick={() => onPick(latest)} data-testid="version-latest">
            Read the latest
          </button>
        ) : null}
      </div>
    </section>
  );
}
