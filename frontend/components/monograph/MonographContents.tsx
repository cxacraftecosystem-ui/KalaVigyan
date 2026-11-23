import { numberWord } from "@/lib/atlasIndex";
import type { ChapterPlan } from "@/lib/monographRenderLayout";

export const CONTENTS_LABEL = "Chapters of this monograph";
export const CONTENTS_DEK = "Each opens the chapter of this page that tells it in full.";

export function contentsKicker(count: number): string {
  return `The monograph in ${numberWord(count)} ${count === 1 ? "chapter" : "chapters"}`;
}

export function MonographContents({ chapters }: { chapters: readonly ChapterPlan[] }) {
  const numbered = chapters.filter((chapter) => chapter.number !== null);
  if (!numbered.length) return null;
  return (
    <div className="bx bx-chem">
      <div className="screen">
        <div className="wrap">
          <div className="spread">
            <div className="main">
              <nav className="toc kv-toc" aria-label={CONTENTS_LABEL}>
                <p className="kicker">{contentsKicker(numbered.length)}</p>
                <p className="kv-toc-d">{CONTENTS_DEK}</p>
                <ol>
                  {numbered.map((chapter) => (
                    <li key={chapter.key}>
                      <a href={`#${chapter.key}`}>
                        <b>{chapter.number}</b>
                        <span>{chapter.label}</span>
                      </a>
                    </li>
                  ))}
                </ol>
              </nav>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
