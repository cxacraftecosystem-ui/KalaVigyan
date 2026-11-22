"use client";

import { useExplainerReading } from "@/components/answer/ExplainerReading";
import { scrollToAnchor } from "@/components/motion/scrollToAnchor";
import { headingView } from "@/lib/answerLanguages";
import type { SectionView } from "@/lib/explainerState";
import { sectionAnchor, workingLabel } from "@/lib/explainerView";

export const SECTION_BAR_MIN = 3;

export function SectionBar({
  sections,
  active,
  streaming,
  onPick
}: {
  sections: readonly SectionView[];
  active: string | null;
  streaming: boolean;
  onPick: (id: string) => void;
}) {
  const { language, original } = useExplainerReading();
  if (sections.length < SECTION_BAR_MIN) return null;
  return (
    <nav aria-label="Sections" className="kv-chapters static mt-10" data-testid="section-bar">
      <ol>
        {sections.map((section, index) => {
          const working = workingLabel(section.state, streaming);
          const heading = headingView({ id: section.id, heading: section.title, original: section.original, sentences: [] }, language, original);
          return (
            <li key={section.id}>
              <a
                href={`#${sectionAnchor(section.id)}`}
                aria-current={section.id === active ? "location" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  onPick(section.id);
                  scrollToAnchor(sectionAnchor(section.id));
                }}
              >
                <b>{index + 1}</b>
                <span lang={heading.lang} dir={heading.dir}>
                  {heading.text}
                </span>
                {working ? <span className="kv-spin" aria-hidden /> : null}
                {working ? <span className="sr-only">, {working.toLowerCase()}</span> : null}
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
