import { DataScript } from "@/components/monograph/DataScript";
import type { MonographDocument } from "@/lib/monographDocument";
import { dataByScope, KIT_CITES_ID, KIT_HIDDEN_SCOPES, KIT_SCOPE_CONTROLS, kitCites } from "@/lib/monographRenderKit";

export const CODA_LINE = "KalaVigyan, from IIT Kharagpur and its Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform. Every sentence opens to its source’s own words.";
const RATES = ["1", "1.25", "1.5"] as const;

function Player() {
  return (
    <div className="kv-player" id="kv-player" role="region" aria-label="Listen to this answer" hidden>
      <div className="kv-wrap">
        <div className="kvp-ctl">
          <button className="kvp-prev" type="button" aria-label="Previous sentence">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M12 3 L6 8 L12 13 Z M4 3 V13" fill="currentColor" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </button>
          <button className="kvp-play" type="button" aria-label="Play" />
          <button className="kvp-next" type="button" aria-label="Next sentence">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M4 3 L10 8 L4 13 Z M12 3 V13" fill="currentColor" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </button>
        </div>
        <div className="kvp-mid">
          <div className="kvp-top">
            <span className="kvp-where" />
            <span className="kvp-status" role="status" />
          </div>
          <div className="kvp-bar" aria-hidden="true">
            <b />
          </div>
          <span className="kvp-t" />
        </div>
        <div className="kvp-end">
          <select className="kvp-rate" aria-label="Reading speed" defaultValue="1">
            {RATES.map((rate) => (
              <option key={rate} value={rate}>{`${rate}×`}</option>
            ))}
          </select>
          <button className="kvp-close" type="button" aria-label="Close the player">
            <svg viewBox="0 0 14 14" aria-hidden="true">
              <path d="M2 2 L12 12 M12 2 L2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export function KitShellTail({ document, dataDeferred = false }: { document: MonographDocument; dataDeferred?: boolean }) {
  const { scoped: allScoped, loose: allLoose } = dataByScope(document.content);
  const scoped = dataDeferred ? Object.fromEntries(KIT_HIDDEN_SCOPES.map((scope) => [scope, [] as string[]])) : allScoped;
  const loose = dataDeferred ? [] : allLoose;
  const data = document.content.data;
  return (
    <>
      <footer className="kv-foot">
        <div className="kv-wrap">
          <p>{CODA_LINE}</p>
        </div>
      </footer>
      <div className="pop" id="kv-pop" role="dialog" aria-labelledby="kv-pop-t" hidden />
      <div className="kv-scrim" id="kv-scrim" hidden />
      <div className="bx bx-rm">
        <div className="toast-zone" id="toasts" aria-live="polite" />
      </div>
      <Player />
      {KIT_HIDDEN_SCOPES.map((scope) => (
        <div className={`bx bx-${scope}`} hidden key={scope}>
          {KIT_SCOPE_CONTROLS.map((control) => (
            <button type="button" id={`${scope}-${control}`} key={control} tabIndex={-1} aria-hidden="true" />
          ))}
          {scoped[scope].map((key) => (
            <DataScript key={key} id={key} value={data[key]} />
          ))}
        </div>
      ))}
      {loose.map((key) => (
        <DataScript key={key} id={key} value={data[key]} />
      ))}
      {dataDeferred ? null : <DataScript id={KIT_CITES_ID} value={kitCites(document.content)} />}
    </>
  );
}
