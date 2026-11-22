"use client";

import { useLayoutEffect, useMemo, useState } from "react";

import { renderBlock } from "@/components/answer/blockRenderers";
import { ExplainerReadingProvider, useExplainerReading } from "@/components/answer/ExplainerReading";
import { FilmSceneProvider } from "@/components/answer/FilmScene";
import { headingView } from "@/lib/answerLanguages";
import type { SectionView } from "@/lib/explainerState";
import { DISCIPLINE_LABEL } from "@/lib/explainerView";
import type { FilmCaption as Caption, FilmScene } from "@/lib/filmScenes";
import type { ListenMark } from "@/lib/listen";
import { listenMarkStore } from "@/lib/listenMarks";

export function FilmCaption({ caption }: { caption: Caption }) {
  const before = caption.mark ? caption.text.slice(0, caption.mark.from) : caption.text;
  const word = caption.mark ? caption.text.slice(caption.mark.from, caption.mark.to) : "";
  const after = caption.mark ? caption.text.slice(caption.mark.to) : "";
  return (
    <p
      lang={caption.lang}
      dir={caption.dir}
      className="min-h-[3.5rem] text-balance text-center font-reading text-lede text-ink-1 md:min-h-[4rem]"
      data-testid="film-caption"
      data-narrated={caption.narrated ? "true" : "false"}
    >
      {before}
      {word ? (
        <mark className="rounded-plate bg-turmeric-wash text-ink-1" data-testid="film-caption-word">
          {word}
        </mark>
      ) : null}
      {after}
    </p>
  );
}

function SceneHeading({ section }: { section: SectionView }) {
  const { language } = useExplainerReading();
  const title = headingView({ id: section.id, heading: section.title, original: section.original, sentences: [] }, language, false);
  return (
    <div className="mb-3 min-w-0">
      <p className="kicker">{DISCIPLINE_LABEL[section.discipline]}</p>
      <p lang={title.lang} dir={title.dir} className="mt-1 font-headline text-h3 text-ink-1">
        {title.text}
      </p>
    </div>
  );
}

export function FilmStage({ scene, progress, mark }: { scene: FilmScene; progress: number; mark: ListenMark | null }) {
  const reading = useExplainerReading();
  const [marks] = useState(() => listenMarkStore(mark));
  useLayoutEffect(() => marks.show(mark), [marks, mark]);
  const narrated = useMemo(() => ({ ...reading, listen: marks }), [reading, marks]);
  const shown = useMemo(() => ({ progress }), [progress]);
  const content = useMemo(() => renderBlock(scene.block), [scene.block]);
  return (
    <div className="relative max-h-[46dvh] min-w-0 overflow-y-auto overscroll-contain rounded-card border border-rule bg-ground p-3 sm:p-5 lg:max-h-[58dvh]" data-testid="film-stage">
      <div key={scene.block.id} className="motion-enter min-w-0" data-testid="film-scene" data-kind={scene.block.kind} data-block-id={scene.block.id}>
        {scene.section ? <SceneHeading section={scene.section} /> : null}
        <ExplainerReadingProvider value={narrated}>
          <FilmSceneProvider value={shown}>{content}</FilmSceneProvider>
        </ExplainerReadingProvider>
      </div>
    </div>
  );
}
