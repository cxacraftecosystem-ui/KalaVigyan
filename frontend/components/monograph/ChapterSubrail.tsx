import type { ChapterSection } from "@/lib/monographNotes";

export const SUBRAIL_LABEL = "In this chapter";

type SubrailProps = { sections: readonly ChapterSection[]; chapter: string };

export function subrailLabel(chapter: string): string {
  return `${SUBRAIL_LABEL}: ${chapter}`;
}

function SubrailNav({ sections, chapter }: SubrailProps) {
  return (
    <nav className="subrail" aria-label={subrailLabel(chapter)}>
      <ol>
        {sections.map((section) => (
          <li key={section.id}>
            <a href={`#${section.id}`}>{section.title}</a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function ChapterSubrail({ sections, chapter }: SubrailProps) {
  if (!sections.length) return null;
  return (
    <div className="bx bx-chem">
      <SubrailNav sections={sections} chapter={chapter} />
    </div>
  );
}

export function FramedSubrail({ sections, chapter }: SubrailProps) {
  if (!sections.length) return null;
  return (
    <div className="bx bx-chem">
      <div className="wrap">
        <SubrailNav sections={sections} chapter={chapter} />
      </div>
    </div>
  );
}
