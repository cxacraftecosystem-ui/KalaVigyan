import type { MonographDocument } from "@/lib/monographDocument";
import { numberedDocument } from "@/lib/monographRenderFigures";
import { pagePlan, type PagePlan } from "@/lib/monographRenderLayout";
import { placedPlan } from "@/lib/monographRenderNear";

export function shownPage(document: MonographDocument): { document: MonographDocument; plan: PagePlan } {
  const plan = placedPlan(document, pagePlan(document));
  return { document: numberedDocument(document, plan), plan };
}
