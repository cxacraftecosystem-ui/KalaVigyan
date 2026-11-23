import { apiFetch } from "@/lib/api";
import { craftComparePath, craftComparisonShape, type CraftComparison } from "@/lib/compareContract";
import { DISTRICT_CRAFTS_PATH, districtCraftsShape, type DistrictCrafts } from "@/lib/districtCraftsContract";
import {
  EXPLAINER_PATH,
  EXPLAINER_VERSION_PATH,
  EXPLAINER_VERSIONS_PATH,
  explainerHistoryShape,
  explainerVersionDocumentShape,
  NOTIFICATION_READ_PATH,
  NOTIFICATIONS_PATH,
  NOTIFICATIONS_READ_ALL_PATH,
  notificationListShape,
  SAVED_EXPLAINER_PATH,
  SAVED_EXPLAINERS_PATH,
  savedExplainerListShape,
  type ExplainerHistory,
  type ExplainerVersionDocument,
  type NotificationList,
  type SavedExplainerList
} from "@/lib/learningContract";
import { answerQuizPath, explainerQuizShape, type ExplainerQuiz } from "@/lib/quizContract";
import { parseShape } from "@/lib/shape";
import { conceptCraftsPageShape, CRAFT_SHARED_SCIENCE_PATH, SHARED_CONCEPT_CRAFTS_PATH, sharedScienceShape, type ConceptCraftsPage, type SharedScience } from "@/lib/sharedScienceContract";

export async function fetchExplainerDocument(explainerId: string, version: number | null): Promise<ExplainerVersionDocument> {
  const path = version === null ? EXPLAINER_PATH(explainerId) : EXPLAINER_VERSION_PATH(explainerId, version);
  return parseShape(explainerVersionDocumentShape, await apiFetch<unknown>(path));
}

export async function fetchExplainerHistory(explainerId: string): Promise<ExplainerHistory> {
  return parseShape(explainerHistoryShape, await apiFetch<unknown>(EXPLAINER_VERSIONS_PATH(explainerId)));
}

export async function fetchSavedExplainers(): Promise<SavedExplainerList> {
  return parseShape(savedExplainerListShape, await apiFetch<unknown>(SAVED_EXPLAINERS_PATH));
}

export async function saveExplainer(explainerId: string): Promise<void> {
  await apiFetch<unknown>(SAVED_EXPLAINER_PATH(explainerId), { method: "PUT" });
}

export async function unsaveExplainer(explainerId: string): Promise<void> {
  await apiFetch<unknown>(SAVED_EXPLAINER_PATH(explainerId), { method: "DELETE" });
}

export async function fetchNotifications(): Promise<NotificationList> {
  return parseShape(notificationListShape, await apiFetch<unknown>(NOTIFICATIONS_PATH));
}

export async function markNoteRead(id: string): Promise<void> {
  await apiFetch<unknown>(NOTIFICATION_READ_PATH(id), { method: "POST" });
}

export async function markAllNotesRead(): Promise<void> {
  await apiFetch<unknown>(NOTIFICATIONS_READ_ALL_PATH, { method: "POST" });
}

export async function fetchDistrictCrafts(districtLgd: number): Promise<DistrictCrafts> {
  return parseShape(districtCraftsShape, await apiFetch<unknown>(DISTRICT_CRAFTS_PATH(districtLgd)));
}

export type ComparedCrafts = { comparison: CraftComparison | null };

export async function fetchComparison(slugs: string[]): Promise<ComparedCrafts> {
  const body = await apiFetch<unknown>(craftComparePath(slugs));
  return { comparison: body === undefined ? null : parseShape(craftComparisonShape, body) };
}

export async function fetchCraftSharedScience(slug: string): Promise<SharedScience> {
  return parseShape(sharedScienceShape, await apiFetch<unknown>(CRAFT_SHARED_SCIENCE_PATH(slug)));
}

export async function fetchConceptCrafts(termKey: string, craft: string | null, offset: number): Promise<ConceptCraftsPage> {
  return parseShape(conceptCraftsPageShape, await apiFetch<unknown>(SHARED_CONCEPT_CRAFTS_PATH(termKey, craft, offset)));
}

export async function fetchExplainerQuiz(answerId: string): Promise<ExplainerQuiz | null> {
  const body = await apiFetch<unknown>(answerQuizPath(answerId));
  return body === undefined ? null : parseShape(explainerQuizShape, body);
}
