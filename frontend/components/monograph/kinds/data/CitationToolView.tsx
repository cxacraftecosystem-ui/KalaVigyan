import { CraftReleaseDoi } from "@/components/openData/CraftReleaseDoi";
import { citationToolShape, type CitePanel } from "@/lib/componentSpecsData";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { parseShape } from "@/lib/shape";

const CRAFT_SUBJECT = "craft:";
const MONOGRAPH_PANEL = "monograph";

export function craftOfSubjects(subjects: readonly string[]): string | null {
  const found = subjects.find((subject) => subject.startsWith(CRAFT_SUBJECT));
  return found ? found.slice(CRAFT_SUBJECT.length) : null;
}

function PanelView({ panel, shown, craft, renderUnit }: { panel: CitePanel; shown: boolean; craft: string | null; renderUnit: ComponentViewProps["renderUnit"] }) {
  const texts = Object.fromEntries(panel.styles.map((style) => [`data-${style.value}`, style.text]));
  return (
    <div className="kv-cp" id={panel.panelId} role="tabpanel" aria-labelledby={panel.tabId} hidden={!shown}>
      <div className={panel.box.join(" ")}>
        <section className="screen" data-aid={panel.aid}>
          <div className={panel.cites.join(" ")}>
            <div className="cite-box" id={panel.boxId ?? undefined}>
              <div className="seg cb-seg" role="group" aria-label="Citation style">
                {panel.styles.map((style, index) => (
                  <button key={style.value} type="button" aria-pressed={index === 0 ? "true" : "false"} {...{ [`data-${panel.styleKey}`]: style.value }}>
                    {style.label}
                  </button>
                ))}
              </div>
              <p className="cb-text" id={panel.textId} {...texts}>
                {renderUnit(panel.text)}
              </p>
              <p className="cb-link">{renderUnit(panel.link)}</p>
              <div className="actions" data-count="1">
                <button className="btn sm" type="button" data-copy={panel.textId}>
                  {panel.copyLabel}
                </button>
              </div>
              {craft && panel.key === MONOGRAPH_PANEL ? <CraftReleaseDoi pageUrl={`/crafts/${craft}`} /> : null}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export function CitationToolView({ component, spec, renderUnit }: ComponentViewProps) {
  const tool = parseShape(citationToolShape, spec);
  const craft = craftOfSubjects(component.subjects);
  return (
    <section className="kv-cite" id="kv-cite" aria-labelledby={tool.titleId}>
      <div className="kv-cite-top">
        <h3 className="kv-sub-h" id={tool.titleId}>
          {renderUnit(tool.title)}
        </h3>
        <div className="kv-tabs" role="tablist" aria-label={tool.tabsLabel}>
          {tool.panels.map((panel, index) => (
            <button
              key={panel.key}
              type="button"
              role="tab"
              id={panel.tabId}
              aria-controls={panel.panelId}
              aria-selected={index === 0 ? "true" : "false"}
              tabIndex={index === 0 ? undefined : -1}
              data-kv-ct={panel.key}
            >
              {panel.label}
            </button>
          ))}
        </div>
      </div>
      {tool.panels.map((panel, index) => (
        <PanelView key={panel.key} panel={panel} shown={index === 0} craft={craft} renderUnit={renderUnit} />
      ))}
    </section>
  );
}
