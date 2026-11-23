import { ReaderTools } from "@/components/monograph/ReaderSettings";
import type { ChapterPlan } from "@/lib/monographRenderLayout";

export const RAIL_LABEL = "Chapters";
export const RAIL_LIST_ID = "kv-rail-list";
export const RAIL_ARROWS = {
  back: { label: "Show earlier chapters", path: "M10 3 L5 8 L10 13" },
  on: { label: "Show later chapters", path: "M6 3 L11 8 L6 13" }
} as const;

type Chapters = { chapters: readonly ChapterPlan[] };

function RailArrow({ go }: { go: keyof typeof RAIL_ARROWS }) {
  const arrow = RAIL_ARROWS[go];
  return (
    <button className="kv-rail-go" type="button" data-go={go} aria-label={arrow.label} aria-controls={RAIL_LIST_ID} hidden>
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d={arrow.path} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

function RailNav({ chapters }: Chapters) {
  return (
    <nav className="kv-rail" aria-label={RAIL_LABEL}>
      <div className="kv-wrap">
        <div className="kv-rail-in">
          <RailArrow go="back" />
          <ol id={RAIL_LIST_ID}>
            {chapters.map((chapter, at) => (
              <li key={chapter.key}>
                <a href={`#${chapter.key}`} aria-current={at === 0 ? "location" : undefined}>
                  {chapter.number !== null ? <b>{chapter.number}</b> : null}
                  <span>{chapter.rail}</span>
                </a>
              </li>
            ))}
          </ol>
          <RailArrow go="on" />
        </div>
      </div>
    </nav>
  );
}

function MenuBar({ chapters }: Chapters) {
  return (
    <div className="kv-menubar">
      <div className="kv-wrap">
        <p id="kv-menu-label">
          <span>{chapters[0]?.label}</span>
        </p>
        <button className="kv-menu-btn" id="kv-menu-btn" type="button" aria-expanded="false" aria-controls="kv-menu">
          <span>{RAIL_LABEL}</span>
          <svg viewBox="0 0 14 14" aria-hidden="true">
            <path d="M3 5 L7 9 L11 5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}

function ChapterMenu({ chapters }: Chapters) {
  return (
    <div className="kv-menu" id="kv-menu" role="dialog" aria-modal="true" aria-label={RAIL_LABEL} hidden>
      <div className="kv-menu-h">
        <p>{RAIL_LABEL}</p>
        <button className="kv-menu-close" type="button" aria-label="Close">
          <svg viewBox="0 0 14 14" aria-hidden="true">
            <path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      <ol>
        {chapters.map((chapter) => (
          <li key={chapter.key}>
            <a href={`#${chapter.key}`}>
              <b>{chapter.number ?? ""}</b>
              <span>{chapter.label}</span>
            </a>
          </li>
        ))}
      </ol>
      <ReaderTools />
    </div>
  );
}

export function MonographRail({ chapters }: Chapters) {
  return (
    <>
      <RailNav chapters={chapters} />
      <MenuBar chapters={chapters} />
      <ChapterMenu chapters={chapters} />
    </>
  );
}
