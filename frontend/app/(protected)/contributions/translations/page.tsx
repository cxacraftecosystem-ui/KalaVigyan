"use client";


import { OpenWorkStarts } from "@/components/contributions/OpenWorkStarts";
import { FormPending } from "@/components/contributions/ProposalFields";
import { TermsConsent } from "@/components/contributions/TermsConsent";
import { TranslationForm } from "@/components/contributions/TranslationForm";
import { TranslationReply } from "@/components/contributions/TranslationReply";
import { TranslationReview } from "@/components/contributions/TranslationReview";
import { useContributions } from "@/components/contributions/useContributions";
import { useTranslationWork } from "@/components/contributions/useTranslationWork";
import { PageHeader } from "@/components/PageHeader";
import { useAuth } from "@/components/AuthProvider";
import { hasRank } from "@/lib/permissions";
import type { TaskKind, TaskSubject } from "@/lib/ownProposalsContract";

const TRANSLATE_KINDS: readonly TaskKind[] = ["TRANSLATE"];
const PAGE_SUBJECTS: readonly TaskSubject["kind"][] = ["craft", "family", "category"];

export default function TranslatePage() {
  const contributions = useContributions();
  const work = useTranslationWork(contributions);
  const { user } = useAuth();
  const { form, error } = contributions;
  return (
    <>
      <PageHeader
        title="Translate a page"
        description="A page in another language is the same page: each sentence translated from its English sentence, keeping its citations, numbers, names and quotes. A reviewer who reads the language approves it."
      />
      <div className="grid gap-12">
        <OpenWorkStarts kinds={TRANSLATE_KINDS} subjects={PAGE_SUBJECTS} disabled={work.busy} onPick={(task) => void work.startFrom(task)} />
        <TranslationForm work={work} />
        {form ? <TermsConsent terms={form.terms} ticked={work.ticked} disabled={work.busy} onTick={work.setTicked} /> : <FormPending failed={Boolean(error)} />}
        <TranslationReply reply={work.reply} sent={work.sent} />
        {work.problems.length ? (
          <ul role="alert" className="grid gap-1 font-ui text-ui text-error">
            {work.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        ) : null}
        {hasRank(user, "PROFESSOR") ? <TranslationReview /> : null}
      </div>
    </>
  );
}
