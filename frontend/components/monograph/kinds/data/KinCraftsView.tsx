import Link from "next/link";
import type { ReactNode } from "react";

import { FamilySwatch } from "@/components/crafts/FamilySwatch";
import type { PlateMaterial } from "@/components/editorial/TypographicPlate";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { parsedSpec } from "@/lib/componentSpecsGeneral";
import { kinCraftsShape, kinMaterial, sharesLine, type KinCraft } from "@/lib/kinCraftsSpec";

function KinRow({ craft, material, renderUnit }: { craft: KinCraft; material: PlateMaterial; renderUnit: (ref: string) => ReactNode }) {
  const shares = sharesLine(craft.shares);
  return (
    <li className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 border-t border-rule py-4" data-testid="kin-craft">
      <FamilySwatch material={material} className="row-span-3 h-12 w-12 rounded-plate border border-ink-2" />
      <Link href={craft.path} className="kv-link min-w-0 break-words font-reading text-h3">
        {craft.name}
      </Link>
      <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 font-ui text-label text-ink-3">
        {craft.place ? <span>{craft.place}</span> : null}
        {craft.gi ? (
          <span className="kicker m-0">
            GI<span className="sr-only"> registered</span>
          </span>
        ) : null}
        {craft.monograph ? <span className="kicker m-0">Monograph</span> : null}
        {shares ? <span className="text-ink-2">{shares}</span> : null}
      </p>
      <p className="min-w-0 max-w-measure font-reading text-body-sm text-ink-1">{renderUnit(craft.sentence)}</p>
    </li>
  );
}

export function KinCraftsView({ component, spec, renderUnit }: ComponentViewProps) {
  const kin = parsedSpec(kinCraftsShape, spec);
  if (!kin) return null;
  const titleId = `${component.label.replaceAll("/", "--")}-title`;
  const material = kinMaterial(kin.head.family);
  return (
    <section className="grid min-w-0 gap-3" aria-labelledby={titleId} data-testid="kin-crafts">
      <h3 id={titleId} className="font-reading text-h3 text-ink-1">
        {kin.head.title}
      </h3>
      <ul className="grid min-w-0 border-b border-rule">
        {kin.crafts.map((craft) => (
          <KinRow key={craft.path} craft={craft} material={material} renderUnit={renderUnit} />
        ))}
      </ul>
    </section>
  );
}
