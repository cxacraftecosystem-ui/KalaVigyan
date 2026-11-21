import type { MonographDocument } from "@/lib/monographDocument";
import type { PagePlan } from "@/lib/monographRenderLayout";
import { documentDigest, leadChapters, shellRestPath } from "@/lib/monographRenderShell";

const CITED_SUBJECT = "craft";

export function railAfterMasthead(document: MonographDocument, plan: PagePlan, masthead: boolean): boolean {
  return document.shell === null && masthead && plan.label !== null && plan.chapters[0]?.index === 0;
}

export function deferredRest(document: MonographDocument, plan: PagePlan, deferred: boolean): string | null {
  if (!deferred) return null;
  if (document.shell !== null) return document.subjectKind === CITED_SUBJECT ? shellRestPath(document.subjectSlug, document.version, CITED_SUBJECT, documentDigest(document)) : null;
  if (plan.chapters.length <= leadChapters(plan.chapters).length) return null;
  return shellRestPath(document.subjectSlug, document.version, document.subjectKind, documentDigest(document));
}
