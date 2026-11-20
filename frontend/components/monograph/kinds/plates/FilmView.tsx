import type { ArtFrame, FilmSpec } from "@/lib/componentSpecsPlates";
import { filmShape } from "@/lib/componentSpecsPlates";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { parseShape } from "@/lib/shape";

import { AiTag, AiTagIcon, DownloadIcon, PAUSE_ICON_MARKUP, PLAY_ICON_MARKUP, PlayIcon } from "./KitIcons";
import { playerTime, sceneName } from "./mediaCopy";

function SceneArt({ art }: { art: ArtFrame }) {
  return (
    <svg viewBox={art.viewBox} preserveAspectRatio="xMidYMid slice" aria-hidden="true" className="">
      <use href={`#${art.symbol}`} width={art.width} height={art.height} />
    </svg>
  );
}

function FilmControls({ film }: { film: FilmSpec }) {
  const playback = film.playback;
  return (
    <div className="film-ctl">
      <button className="vid-play" type="button" id="film-play" aria-label="Play the film" data-play={PLAY_ICON_MARKUP} data-pause={PAUSE_ICON_MARKUP}>
        <PlayIcon />
      </button>
      <div>
        <div className="film-ticks" id="film-ticks">
          {film.scenes.map((scene, index) => (
            <i key={scene.title} className={index === 0 ? "ready cur" : "ready"}></i>
          ))}
        </div>
        <input className="vid-range" type="range" id="film-range" min={0} max={playback.durationMs} step={playback.stepMs} defaultValue={playback.restMs} aria-label="Film position" />
      </div>
      <span className="vid-time" id="film-time">
        {playerTime(playback.restMs, playback.durationMs)}
      </span>
    </div>
  );
}

function FilmStrip({ film }: { film: FilmSpec }) {
  return (
    <ol className="film-strip" id="film-strip" aria-label="Scenes">
      {film.scenes.map((scene, index) => (
        <li key={scene.title}>
          <button
            className={scene.forming ? "fs-b forming" : "fs-b"}
            type="button"
            data-scene={index}
            aria-pressed={index === 0 ? "true" : "false"}
            aria-disabled={scene.forming ? "true" : undefined}
            aria-label={sceneName(index + 1, scene.title, scene.forming)}
          >
            <span className="fs-th">
              <SceneArt art={scene.art} />
            </span>
            <span className="fs-n">{index + 1}</span>
            <span className="fs-t">{scene.field}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

function FilmLabels({ film }: { film: FilmSpec }) {
  return (
    <div className="film-labels">
      <span className="tagline">
        {film.tags.map((tag) => (
          <span key={tag} className="tag-s">
            <AiTagIcon />
            {tag}
          </span>
        ))}
      </span>
      <span className="fl-text" id="film-note">{`${film.note} `}</span>
      <span className="fl-act">
        <button className="dl" type="button" id="film-dl" data-name={film.downloadName}>
          <DownloadIcon />
          Download film
        </button>
        <button className="dl" type="button" id="film-vtt" data-name={film.subtitlesName}>
          <DownloadIcon />
          Subtitles
        </button>
      </span>
    </div>
  );
}

export function FilmView({ spec, renderUnit }: ComponentViewProps) {
  const film = parseShape(filmShape, spec);
  return (
    <div className="film-block ai-only" id="film-block">
      <div className="film-h">
        <h3>{renderUnit(film.title)}</h3>
        <p className="film-meta" id="film-meta">
          {renderUnit(film.meta)}
        </p>
      </div>
      <div className="film" id="film">
        <div className="film-stage">
          {film.scenes.map((scene, index) => (
            <div key={scene.title} className={index === 0 ? "film-scene on" : "film-scene"} data-scene={index}>
              <SceneArt art={scene.art} />
            </div>
          ))}
          <p className="film-scene-l" id="film-scene-l">
            {renderUnit(film.sceneLabel)}
          </p>
          <p className="film-sub" id="film-sub">
            {renderUnit(film.subtitle)}
          </p>
          <FilmControls film={film} />
          <AiTag label={film.tags[0]} />
        </div>
      </div>
      <FilmStrip film={film} />
      <FilmLabels film={film} />
    </div>
  );
}
