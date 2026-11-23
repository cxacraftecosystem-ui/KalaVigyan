"use client";

import { useExplainerReading } from "@/components/answer/ExplainerReading";
import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { SentencesDiffer } from "@/components/answer/SentencesDiffer";
import { scriptLeading, textScript } from "@/lib/answerEssay";
import { paragraphAttributes } from "@/lib/answerLanguages";
import type { ExplainerSentence as Sentence } from "@/lib/explainerBlockBase";
import type { ProseBlock } from "@/lib/explainerContract";
import { cn } from "@/lib/utils";

export function CitedText({ id, sentences, className }: { id: string; sentences: readonly Sentence[]; className: string }) {
  const { language, original } = useExplainerReading();
  const paragraph = paragraphAttributes({ id, heading: "", sentences: [...sentences] }, language, original);
  const script = textScript(paragraph.lang, language);
  return (
    <>
      <p lang={paragraph.lang} dir={paragraph.dir} data-script={script ?? undefined} className={cn(className, scriptLeading(script, "prose"))}>
        {sentences.map((sentence) => (
          <ExplainerSentence key={sentence.id} sentence={sentence} />
        ))}
      </p>
      <SentencesDiffer sentences={sentences} />
    </>
  );
}

export function ProseBlockView({ block }: { block: ProseBlock }) {
  return <CitedText id={block.id} sentences={block.sentences} className="font-reading text-body text-ink-1" />;
}
