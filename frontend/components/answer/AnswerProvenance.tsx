import { TextLink } from "@/components/ui/TextLink";
import { answeredOn, answerProvenance } from "@/lib/answerEssay";
import type { AnswerLanguage } from "@/lib/answerLanguages";
import type { CraftLink } from "@/lib/answerShapes";
import { PROVENANCE_ENGLISH, PROVENANCE_KEY, wordAttributes, wordedIn } from "@/lib/interfaceWords";
import type { SourceRef } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ProvenanceFacts = { sources: readonly SourceRef[]; craft: CraftLink | null; answeredAt: string | null; language: AnswerLanguage | null };

function ReliabilityStrip({ sources }: { sources: readonly SourceRef[] }) {
  const provenance = answerProvenance(sources);
  if (provenance.grades.length === 0) return null;
  return (
    <bdi dir="ltr">
      <span className="inline-flex items-center gap-2.5" role="img" aria-label={provenance.spoken} data-testid="reliability-strip">
        {provenance.grades.map((grade) => (
          <span key={grade.grade} className="inline-flex items-center gap-1 lining-nums tabular-nums">
            <span aria-hidden className="kv-rel" data-grade={grade.grade} />
            {`${grade.grade} ${grade.count}`}
          </span>
        ))}
      </span>
    </bdi>
  );
}

export function AnswerProvenance({ facts, inline = false, className }: { facts: ProvenanceFacts; inline?: boolean; className?: string }) {
  const worded = wordedIn(facts.language, PROVENANCE_KEY, PROVENANCE_ENGLISH);
  const answered = answeredOn(facts.answeredAt, worded);
  return (
    <p
      className={cn(
        "font-ui text-label text-ink-3",
        inline ? "mb-5 flex flex-wrap items-center gap-x-3.5 gap-y-1.5" : "flex flex-col items-start gap-[7px] border-t border-ink-1 pt-3.5",
        className
      )}
      data-testid="answer-provenance"
    >
      <span {...wordAttributes(worded.language, "kicker text-ink-1")}>{worded.words.answer}</span>
      {facts.sources.length > 0 ? <span {...wordAttributes(worded.language)}>{answerProvenance(facts.sources, worded.words).sources}</span> : null}
      <ReliabilityStrip sources={facts.sources} />
      {facts.craft ? <TextLink href={facts.craft.path}>{facts.craft.name}</TextLink> : null}
      {answered ? <span {...wordAttributes(worded.language)}>{answered}</span> : null}
    </p>
  );
}
