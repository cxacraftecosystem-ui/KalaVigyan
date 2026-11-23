"use client";

import type { ReactNode } from "react";

import { CitationChips } from "@/components/answer/CitationContext";
import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { SentencesDiffer } from "@/components/answer/SentencesDiffer";
import { EvidenceTag, SourcesDifferNote } from "@/components/editorial/EvidenceMark";
import { TextLink } from "@/components/ui/TextLink";
import type { CraftLink } from "@/lib/answerShapes";
import { evidenceState } from "@/lib/citationCluster";
import type { LadderStage } from "@/lib/explainerContract";
import { MATERIAL_KIND_LABEL, MATERIAL_ROLE_LABEL, STAGE_TYPE_LABEL } from "@/lib/processView";
import { cn } from "@/lib/utils";

function StageFacts({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-3 min-w-0">
      <h4 className="font-ui text-label text-ink-3">{title}</h4>
      <ul className="mt-1 grid gap-1 font-reading text-body-sm text-ink-1">{children}</ul>
    </section>
  );
}

function materialRole(material: LadderStage["materials"][number]): string {
  const role = MATERIAL_ROLE_LABEL[material.role];
  const kind = MATERIAL_KIND_LABEL[material.kind];
  return role === kind ? role : `${role} · ${kind}`;
}

function reactionLabel(count: number): string {
  return count === 1 ? "See the reaction" : `See the ${count} reactions`;
}

function Materials({ stage }: { stage: LadderStage }) {
  if (stage.materials.length === 0) return null;
  return (
    <StageFacts title="Materials">
      {stage.materials.map((material) => (
        <li key={material.materialId}>
          <span>{material.name}</span>
          {material.botanicalName ? <i className="text-ink-2"> {material.botanicalName}</i> : null}
          <span className="font-ui text-label text-ink-3"> · {materialRole(material)}</span>
          <CitationChips citations={material.citations} />
        </li>
      ))}
    </StageFacts>
  );
}

function Conditions({ stage }: { stage: LadderStage }) {
  const tools = stage.tools ?? [];
  if (stage.conditions.length === 0 && tools.length === 0) return null;
  return (
    <StageFacts title="Conditions and tools">
      {stage.conditions.map((condition, index) => (
        <li key={`${condition.label}:${index}`} data-testid="ladder-condition">
          <span className="font-ui text-label text-ink-3">{condition.label}: </span>
          {condition.stated}
          <CitationChips citations={condition.citations} />
        </li>
      ))}
      {tools.map((tool) => (
        <li key={tool.toolId}>
          {tool.name}
          {tool.localNames.length > 0 ? <i className="text-ink-2"> {tool.localNames.join(", ")}</i> : null}
          <CitationChips citations={tool.citations} />
        </li>
      ))}
    </StageFacts>
  );
}

function Differs({ stage }: { stage: LadderStage }) {
  return (stage.differs ?? []).map((differ) => (
    <SourcesDifferNote key={differ.key} summary={differ.about}>
      {differ.readings.map((reading, index) => (reading.sentence ? <ExplainerSentence key={`${differ.key}:${index}`} sentence={reading.sentence} /> : null))}
    </SourcesDifferNote>
  ));
}

export function LadderStageCard({ stage, craft, reached }: { stage: LadderStage; craft: CraftLink; reached: boolean }) {
  const state = evidenceState({ evidence: "QUOTED", level: stage.level });
  return (
    <li className={cn("grid min-w-0 grid-cols-[2.5rem_minmax(0,1fr)] gap-x-3 border-b border-s-2 border-b-rule py-4 ps-3 sm:grid-cols-[3rem_minmax(0,1fr)]", reached ? "border-s-ink-1" : "border-s-transparent")} data-testid="ladder-stage" data-reached={reached ? "true" : "false"}>
      <span aria-hidden className={cn("grid h-8 w-8 place-items-center rounded-plate font-ui text-label tabular-nums", reached ? "bg-ink-1 text-ground" : "bg-sunk text-ink-3")}>
        {stage.ordinal}
      </span>
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 font-ui text-caption text-ink-3">
          {STAGE_TYPE_LABEL[stage.stageType]}
          {state !== "verified" ? <EvidenceTag state={state} /> : null}
        </p>
        <h3 className="mt-0.5 break-words font-reading text-h3 text-ink-1">
          <span className="sr-only">Step {stage.ordinal}: </span>
          {stage.localName ? <i>{stage.localName}</i> : null}
          {stage.localName ? " · " : null}
          {stage.name}
        </h3>
        {stage.sentences.length > 0 || stage.why ? (
          <p className="mt-1.5 font-reading text-body-sm text-ink-1">
            {stage.sentences.map((sentence) => (
              <ExplainerSentence key={sentence.id} sentence={sentence} />
            ))}
            {stage.why ? <ExplainerSentence sentence={stage.why} /> : null}
          </p>
        ) : null}
        <SentencesDiffer sentences={stage.why ? [...stage.sentences, stage.why] : stage.sentences} />
        <Differs stage={stage} />
        {stage.after ? (
          <p className="mt-2 font-reading text-body-sm text-ink-2" data-cite-host="">
            <span className="font-ui text-label text-ink-3">Cloth after: </span>
            {stage.after.text}
            <CitationChips citations={stage.after.citations} />
          </p>
        ) : null}
        <Materials stage={stage} />
        <Conditions stage={stage} />
        {stage.reactionIds.length > 0 ? (
          <p className="mt-3">
            <TextLink href={`${craft.path}?tab=process`} standalone>
              {reactionLabel(stage.reactionIds.length)}
            </TextLink>
          </p>
        ) : null}
      </div>
    </li>
  );
}
