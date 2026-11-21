import { KIT_DEFS, KIT_STYLE_REFERENCES } from "@/generated/kitDefs";
import type { MonographDocument } from "@/lib/monographDocument";
import { defsByScope, pageDefs } from "@/lib/monographKitDefs";

const HIDDEN = { position: "absolute", width: 0, height: 0, overflow: "hidden" } as const;

export function KitDefs({ document }: { document: MonographDocument }) {
  const scoped = defsByScope(pageDefs(document, KIT_DEFS, KIT_STYLE_REFERENCES));
  if (!scoped.length) return null;
  return (
    <div aria-hidden="true" style={HIDDEN} data-testid="kit-defs">
      {scoped.map(({ scope, markup }) => (
        <div key={scope ?? "page"} className={scope ? `bx bx-${scope}` : undefined} style={HIDDEN}>
          <svg className="kv-defs" width="0" height="0" focusable="false">
            <defs dangerouslySetInnerHTML={{ __html: markup.join("") }} />
          </svg>
        </div>
      ))}
    </div>
  );
}
