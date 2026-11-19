"use client";

import { useState } from "react";
import { Check } from "lucide-react";

import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { PictureView } from "@/components/answer/ImageStrip";
import type { QuizBlock } from "@/lib/explainerLearning";
import { countNoun } from "@/lib/format";
import type { LessonPack, Slide } from "@/lib/lessonContract";
import { slideCaption } from "@/lib/lessonView";
import { cn } from "@/lib/utils";

function SlidePicture({ slide }: { slide: Slide }) {
  const [broken, setBroken] = useState(false);
  if (!slide.image || broken) return null;
  return (
    <div className="max-w-xs">
      <PictureView media={slide.image} onBroken={() => setBroken(true)} />
    </div>
  );
}

function QuizBody({ quiz, index }: { quiz: QuizBlock | null; index: number | null }) {
  const question = quiz && index !== null ? quiz.questions[index] : undefined;
  if (!question) return null;
  return (
    <div className="grid min-w-0 gap-2">
      <p className="break-words font-reading text-body-sm text-ink-1">{question.prompt}</p>
      <ul className="grid gap-1">
        {question.options.map((option, place) => (
          <li key={option.termKey} className="flex min-w-0 items-start gap-2 font-ui text-ui font-normal text-ink-2">
            {place === question.answer ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden /> : <span className="h-4 w-4 shrink-0" aria-hidden />}
            <span className={cn("min-w-0 break-words", place === question.answer && "text-ink-1")}>{option.text}</span>
            {place === question.answer ? <span className="sr-only">(answer)</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SlideBody({ slide, pack }: { slide: Slide; pack: LessonPack }) {
  if (slide.kind === "SECTION") {
    return (
      <div className="grid min-w-0 gap-3">
        <ul className="grid list-disc gap-1.5 ps-5 font-reading text-body-sm text-ink-1 marker:text-ink-3">
          {slide.bullets.map((bullet) => (
            <li key={bullet.id} className="break-words">
              <ExplainerSentence sentence={bullet} />
            </li>
          ))}
        </ul>
        <SlidePicture slide={slide} />
      </div>
    );
  }
  if (slide.kind === "QUIZ") return <QuizBody quiz={pack.quiz} index={slide.question} />;
  if (slide.kind === "READING") return <p className="font-ui text-ui font-normal text-ink-2 tabular-nums">{countNoun(pack.readingList.length, "reading")}</p>;
  if (slide.kind === "SOURCES") return <p className="font-ui text-ui font-normal text-ink-2 tabular-nums">{countNoun(pack.sources.length, "source")}</p>;
  return pack.craft ? <p className="font-ui text-ui font-normal text-ink-2">{pack.craft.name}</p> : null;
}

export function SlidePreview({ pack }: { pack: LessonPack }) {
  const total = pack.slides.length;
  return (
    <ol className="grid min-w-0 gap-4 md:grid-cols-2" aria-label="Slides" data-testid="slides">
      {pack.slides.map((slide) => (
        <li
          key={slide.number}
          className={cn("grid min-w-0 content-start gap-3 rounded-plate border border-rule p-4 md:p-5", slide.kind === "TITLE" && "bg-sunk md:col-span-2")}
          data-testid="slide"
          data-kind={slide.kind}
        >
          <p className="kicker tabular-nums">{slideCaption(slide, total)}</p>
          <h3 className={cn("break-words text-ink-1", slide.kind === "TITLE" ? "font-headline text-h2" : "font-reading text-h3")}>{slide.title}</h3>
          <SlideBody slide={slide} pack={pack} />
        </li>
      ))}
    </ol>
  );
}
