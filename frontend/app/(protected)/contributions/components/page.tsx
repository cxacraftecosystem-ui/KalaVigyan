"use client";


import { ComponentForm } from "@/components/contributions/ComponentForm";
import { ComponentResult } from "@/components/contributions/ComponentResult";
import { LibrarySearch } from "@/components/contributions/LibrarySearch";
import { ContributionsSection } from "@/components/contributions/MyContributions";
import { OpenWorkStarts } from "@/components/contributions/OpenWorkStarts";
import { FormPending } from "@/components/contributions/ProposalFields";
import { useComponentProposal } from "@/components/contributions/useComponentProposal";
import { useContributions } from "@/components/contributions/useContributions";
import { useLibrarySearch } from "@/components/contributions/useLibrarySearch";
import { PageHeader } from "@/components/PageHeader";
import { TextLink } from "@/components/ui/TextLink";
import { COMPONENT_TASK_KINDS, COMPONENT_TASK_SUBJECTS, type OpenTask } from "@/lib/ownProposalsContract";

export default function ProposeComponentPage() {
  const contributions = useContributions();
  const proposal = useComponentProposal(contributions);
  const library = useLibrarySearch();
  const { form, error, notice } = contributions;

  function startFrom(task: OpenTask) {
    proposal.startFrom(task);
    if (task.subject) library.setCraft({ slug: task.subject.slug, name: task.subject.name });
  }

  return (
    <>
      <PageHeader
        title="Propose a component"
        description="A 3D molecule, a what-if, a map, a reaction player or a plate of pictures that a craft's page can place. Search the library first: what it holds is placed or extended, never copied."
      />
      <div className="grid gap-12">
        <p className="font-ui text-ui text-ink-2">
          A single fact instead? <TextLink href="/contributions/facts">Propose a fact</TextLink>
        </p>
        <OpenWorkStarts kinds={COMPONENT_TASK_KINDS} subjects={COMPONENT_TASK_SUBJECTS} disabled={proposal.busy} onPick={startFrom} />
        {form ? <LibrarySearch library={library} form={form} proposal={proposal} /> : <FormPending failed={Boolean(error)} />}
        {form && proposal.describing ? <ComponentForm proposal={proposal} form={form} /> : null}
        <ComponentResult proposal={proposal} form={form} />
        {notice ? <p role="status" className="font-ui text-ui text-ink-1">{notice}</p> : null}
        {error ? <p role="alert" className="font-ui text-ui text-error">{error}</p> : null}
        <ContributionsSection title="Your components" kind="COMPONENT" empty="Components you propose appear here with what an Admin decided. Withdraw one while it waits for review." contributions={contributions} />
      </div>
    </>
  );
}
