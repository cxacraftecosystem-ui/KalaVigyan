import { TextLink } from "@/components/ui/TextLink";
import { answerProvenance } from "@/lib/answerEssay";
import type { CraftLink } from "@/lib/answerShapes";
import type { SourceRef } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ProvenanceFacts = { sources: readonly SourceRef[]; craft: CraftLink | null; answered: string | null };

function ReliabilityStrip({ sources }: { sources: readonly SourceRef[] }) {
  const provenance = answerProvenance(sources);
  if (provenance.grades.length === 0) return null;
  return (
    <bdi dir="ltr">
      <span className="inline-flex items-center gap-2.5" role="img" aria-label={provenance.spoken} data-testid="reliability-strip">
        {provenance.grades.map((grade) => (
          <span key={grade.grade} className="inline-flex items-center gap-1 lining-nums tabular-nums">
            <span aria-hidden className="kv-rel" data-grade={grade.grade} />
            {`${grade.grade} ${grade.count}`}
          </span>
        ))}
      </span>
    </bdi>
  );
}

export function AnswerProvenance({ facts, inline = false, className }: { facts: ProvenanceFacts; inline?: boolean; className?: string }) {
  return (
    <p
      className={cn(
        "font-ui text-label text-ink-3",
        inline ? "mb-5 flex flex-wrap items-center gap-x-3.5 gap-y-1.5" : "flex flex-col items-start gap-[7px] border-t border-ink-1 pt-3.5",
        className
      )}
      data-testid="answer-provenance"
    >
      <span className="kicker text-ink-1">Answer</span>
      {facts.sources.length > 0 ? <span>{answerProvenance(facts.sources).sources}</span> : null}
      <ReliabilityStrip sources={facts.sources} />
      {facts.craft ? <TextLink href={facts.craft.path}>{facts.craft.name}</TextLink> : null}
      {facts.answered ? <span>{facts.answered}</span> : null}
    </p>
  );
}
