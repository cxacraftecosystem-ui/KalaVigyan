import { DISCIPLINES, type Discipline } from "@/lib/explainerBlockBase";
import { DISCIPLINE_LABEL } from "@/lib/explainerView";
import type { FieldCoverage } from "@/lib/fieldCoverage";

export const FIELD_CHAPTER: Record<Discipline, string> = {
  OVERVIEW: "glance",
  PROCESS: "made",
  CHEMISTRY: "chem",
  PHYSICS: "chem",
  MATERIALS: "made",
  GEOGRAPHY: "why",
  GEOLOGY: "why",
  CLIMATE: "why",
  ECOLOGY: "why",
  BOTANY: "chem",
  HISTORY: "history",
  ECONOMICS: "market",
  DESIGN: "people",
  HEALTH: "made",
  SOCIETY: "people",
  POLICY: "market"
};

export type FieldLead = { slug: string; name: string; facts: number; href: string };
export type FieldHolding = { field: Discipline; label: string; crafts: number; lead: FieldLead | null };
export type FieldHoldings = { monographs: number; fields: FieldHolding[] };

function leadOf(coverages: readonly FieldCoverage[], field: Discipline): FieldLead | null {
  let lead: FieldLead | null = null;
  for (const coverage of coverages) {
    const facts = coverage.fields.find((count) => count.field === field)?.claims ?? 0;
    if (facts > 0 && (!lead || facts > lead.facts || (facts === lead.facts && coverage.name.localeCompare(lead.name, "en") < 0))) {
      lead = { slug: coverage.subjectSlug, name: coverage.name, facts, href: `/crafts/${encodeURIComponent(coverage.subjectSlug)}#${FIELD_CHAPTER[field]}` };
    }
  }
  return lead;
}

export function fieldHoldings(coverages: readonly FieldCoverage[]): FieldHoldings {
  const fields = DISCIPLINES.map((field) => {
    const counts = coverages.map((coverage) => coverage.fields.find((count) => count.field === field)?.claims ?? 0);
    return {
      field,
      label: DISCIPLINE_LABEL[field],
      crafts: counts.filter((count) => count > 0).length,
      lead: leadOf(coverages, field)
    };
  });
  return { monographs: coverages.length, fields };
}

function fewest(holdings: FieldHoldings): FieldHolding | null {
  return holdings.fields.reduce<FieldHolding | null>((low, field) => (low === null || field.crafts < low.crafts ? field : low), null);
}

export function fieldsFinding(holdings: FieldHoldings): string | null {
  const total = holdings.monographs;
  const low = fewest({ ...holdings, fields: holdings.fields.filter((field) => field.crafts > 0) });
  if (total === 0 || !low) return null;
  const count = holdings.fields.length;
  const full = holdings.fields.filter((field) => field.crafts === total).length;
  if (full === count) return `All ${total} monographs hold cited facts in all ${count} fields.`;
  if (full === 0) return `${low.label} is in ${low.crafts} of the ${total} monographs, the fewest.`;
  return `All ${total} monographs hold cited facts in ${full} of the ${count} fields; ${low.label.toLowerCase()} is in ${low.crafts}, the fewest.`;
}
