import { expect, test } from "@playwright/test";

import { districtCraftsShape, DISTRICT_CRAFTS_PATH } from "@/lib/districtCraftsContract";
import {
  buildsOnEventShape,
  buildsOnShape,
  EXPLAINER_VERSION_PATH,
  explainerHistoryShape,
  explainerVersionDocumentShape,
  hasNewerVersion,
  notificationListShape,
  SAVED_EXPLAINER_PATH,
  savedExplainerListShape
} from "@/lib/learningContract";
import { CITATIONS_FILE_PATH, citationExportShape, LESSON_FILE_PATH, lessonListShape, lessonPackShape, lessonRequestShape } from "@/lib/lessonContract";
import { canBuildLessons } from "@/lib/permissions";
import { conceptCraftsPageShape, CRAFT_SHARED_SCIENCE_PATH, SHARED_CONCEPT_CRAFTS_PATH, sharedConceptShape, sharedScienceShape } from "@/lib/sharedScienceContract";
import { parseShape, ShapeError, type Shape } from "@/lib/shape";
import type { User, UserRole } from "@/lib/types";

import { readRepo } from "./phaseBFixture";

type Golden = Record<string, unknown>;

function golden(name: string): Golden {
  return JSON.parse(readRepo("shared", name)) as Golden;
}

function exactly<T>(shape: Shape<T>, value: unknown) {
  expect(parseShape(shape, value) as unknown).toEqual(value);
}

const VERSIONS = golden("learning.versions.golden.json");
const ALERTS = golden("learning.alerts.golden.json");
const LESSON = golden("learning.lesson.golden.json");

test("follow-up versions parse exactly as the backend writes them", () => {
  exactly(explainerHistoryShape, VERSIONS.history);
  exactly(explainerVersionDocumentShape, VERSIONS.latest);
  exactly(buildsOnShape, VERSIONS.request);
  exactly(buildsOnEventShape, VERSIONS.buildsOn);
  const latest = VERSIONS.latest as { mark: { changes: unknown[] } };
  expect(latest.mark.changes).toHaveLength(2);
});

test("saved explainers and notes parse, and a saved answer seen at an older version shows as newer", () => {
  exactly(savedExplainerListShape, ALERTS.saved);
  exactly(notificationListShape, ALERTS.notifications);
  const saved = parseShape(savedExplainerListShape, ALERTS.saved).items[0];
  expect(hasNewerVersion(saved)).toBe(false);
  expect(hasNewerVersion({ ...saved, seenVersion: 1 })).toBe(true);
});

test("a lesson pack, its request and the lesson list parse exactly", () => {
  exactly(lessonRequestShape, LESSON.request);
  exactly(lessonPackShape, LESSON.pack);
  exactly(lessonListShape, LESSON.list);
  const pack = structuredClone(LESSON.pack) as { slides: Record<string, unknown>[] };
  pack.slides[0] = { ...pack.slides[0], kind: "COVER" };
  expect(() => parseShape(lessonPackShape, pack)).toThrow(ShapeError);
});

test("citations, shared science and a tapped district parse exactly", () => {
  exactly(citationExportShape, golden("learning.citations.golden.json"));
  const shared = golden("learning.shared-science.golden.json");
  exactly(sharedScienceShape, shared.craft);
  exactly(sharedConceptShape, shared.concept);
  exactly(conceptCraftsPageShape, shared.crafts);
  exactly(districtCraftsShape, golden("map.district-crafts.golden.json"));
});

test("routes are named once and escaped", () => {
  expect(EXPLAINER_VERSION_PATH("a b", 2)).toBe("/explainers/a%20b/versions/2");
  expect(SAVED_EXPLAINER_PATH("x")).toBe("/saved-explainers/x");
  expect(LESSON_FILE_PATH("l1", "pptx")).toBe("/lessons/l1/files/pptx");
  expect(CITATIONS_FILE_PATH("e1", 1, "ris")).toBe("/explainers/e1/versions/1/citations/ris");
  expect(CRAFT_SHARED_SCIENCE_PATH("Kutch-Ajrakh")).toBe("/crafts/Kutch-Ajrakh/shared-science");
  expect(SHARED_CONCEPT_CRAFTS_PATH("alum", "Kutch-Ajrakh", 100)).toBe("/shared-science/alum/crafts?craft=Kutch-Ajrakh&offset=100");
  expect(SHARED_CONCEPT_CRAFTS_PATH("alum", null, 0)).toBe("/shared-science/alum/crafts?offset=0");
  expect(DISTRICT_CRAFTS_PATH(449)).toBe("/map/districts/449");
});

test("professors and above build lesson packs", () => {
  const person = (role: UserRole): User => ({ id: role, email: `${role}@example.org`, name: role, role });
  const ladder: UserRole[] = ["STUDENT", "RESEARCHER", "PROFESSOR", "ADMIN", "MASTER_ADMIN"];
  expect(ladder.map((role) => canBuildLessons(person(role)))).toEqual([false, false, true, true, true]);
});
