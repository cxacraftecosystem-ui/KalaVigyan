"use client";

import { Circle, Diamond, type LucideIcon } from "lucide-react";

import { ChemEquation } from "@/components/answer/ChemEquation";
import { CAST_ROLE_LABEL, type CastMember, type CastRole } from "@/lib/reactionPlayer";
import { cn } from "@/lib/utils";

const ROLE_MARK: Record<CastRole, LucideIcon> = { REACTANT: Circle, PRODUCT: Diamond };
const CARRIED_LABEL = "Intermediate";

function RoleMark({ role }: { role: CastRole }) {
  const Icon = ROLE_MARK[role];
  return <Icon className="h-2.5 w-2.5 shrink-0 fill-current text-ink-1" aria-hidden />;
}

function CastChip({ member, role, carried }: { member: CastMember; role: CastRole | null; carried: boolean }) {
  return (
    <li
      title={member.name}
      data-testid="cast-species"
      data-role={role ?? "none"}
      data-carried={carried ? "true" : undefined}
      className={cn(
        "inline-flex min-h-8 max-w-full items-center gap-1.5 rounded-plate border px-2 font-ui text-ui font-normal transition-colors duration-state",
        role ? "border-ink-1 bg-raised text-ink-1" : "border-rule text-ink-3"
      )}
    >
      {role ? <RoleMark role={role} /> : null}
      {member.formula ? <ChemEquation equation={member.formula} display={false} label={member.name} /> : <span className="min-w-0 break-words text-label">{member.name}</span>}
      {role ? <span className="sr-only">{`, ${CAST_ROLE_LABEL[role]}`}</span> : null}
      {carried ? <span className="bg-turmeric-wash px-1.5 text-caption font-semibold text-ink-1">{CARRIED_LABEL}</span> : null}
    </li>
  );
}

type CastProps = { cast: readonly CastMember[]; roles: ReadonlyMap<string, CastRole>; carried?: ReadonlySet<string> };

export function SpeciesCast({ cast, roles, carried = new Set() }: CastProps) {
  return (
    <div className="min-w-0 bg-sunk p-3" data-testid="species-cast">
      <ul className="flex min-w-0 flex-wrap gap-1.5" aria-label="Species in this reaction">
        {cast.map((member) => (
          <CastChip key={member.key} member={member} role={roles.get(member.key) ?? null} carried={carried.has(member.key)} />
        ))}
      </ul>
      <p aria-hidden className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 font-ui text-caption text-ink-3">
        {(["REACTANT", "PRODUCT"] as const).map((role) => (
          <span key={role} className="inline-flex items-center gap-1.5">
            <RoleMark role={role} />
            {`${CAST_ROLE_LABEL[role]}s`}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="bg-turmeric-wash px-1.5 font-semibold text-ink-1">{CARRIED_LABEL}</span>
          made in one step, used in the next
        </span>
      </p>
    </div>
  );
}
