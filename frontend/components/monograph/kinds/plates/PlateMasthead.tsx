import type { ReactNode } from "react";

import type { GradeCount, MastheadLabel } from "@/lib/componentSpecsPlates";
import { formatCalendarDay } from "@/lib/format";

import { HeldText } from "./HeldText";
import { SpecDrawing } from "./SpecDrawing";

export function reliabilityLabel(sources: number, grades: readonly GradeCount[]): string {
  return `Reliability of the ${sources} sources: ${grades.map((grade) => `${grade.count} graded ${grade.grade}`).join(", ")}`;
}

export function PlateMasthead({ label, renderUnit }: { label: MastheadLabel; renderUnit: (ref: string) => ReactNode }) {
  return (
    <div className="label-card mast-label on-photo kv-open-label" data-size="title">
      <p className="lc-k">{renderUnit(label.kicker)}</p>
      <p className="lc-title">{renderUnit(label.title)}</p>
      <div className="lc-meta">
        <span className="seal">
          <SpecDrawing element={label.seal} />
          <HeldText nodes={label.registration} />
        </span>
        <span>{label.place}</span>
      </div>
      <p className="lc-prov">
        <span>{`Monograph drawn from ${label.sources} sources`}</span>
        <span className="rel-strip" role="img" aria-label={reliabilityLabel(label.sources, label.grades)}>
          {label.grades.map((grade) => (
            <span key={grade.grade} className="rs-g">
              <span className={`rel ${grade.grade}`} aria-hidden="true"></span>
              {`${grade.grade} ${grade.count}`}
            </span>
          ))}
        </span>
        <span>{`Curated ${formatCalendarDay(label.curated)}`}</span>
      </p>
    </div>
  );
}
