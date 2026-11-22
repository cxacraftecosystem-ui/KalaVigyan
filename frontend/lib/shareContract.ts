import { apiFetch } from "@/lib/api";
import { answerLanguagesOf, type AnswerLanguage } from "@/lib/answerLanguages";
import { INSTANT } from "@/lib/answerShapes";
import { EXPLAINER_VERSION_PATH, explainerVersionDocumentShape, type ExplainerVersionDocument } from "@/lib/learningContract";
import { LESSON_PATH, lessonPackShape, type LessonPack } from "@/lib/lessonContract";
import { boolean, matching, nullable, object, oneOf, parseShape, ShapeError, type Shape } from "@/lib/shape";

export const SHARE_TOKEN = /^[A-Za-z0-9_-]{22,64}$/;
export const ANSWER_LANGUAGES_PATH = "/answers/languages";
export const SHARED_ANSWER_PAGE = "/shared/answers";
export const SHARED_LESSON_PAGE = "/shared/lessons";
export const SHARED_ANSWER_PATH = (token: string) => `/shared/answers/${encodeURIComponent(token)}`;
export const SHARED_LESSON_PATH = (token: string) => `/shared/lessons/${encodeURIComponent(token)}`;
export const EXPLAINER_SHARE_PATH = (explainerId: string, version: number) => `${EXPLAINER_VERSION_PATH(explainerId, version)}/share`;
export const LESSON_SHARE_PATH = (lessonId: string) => `${LESSON_PATH(lessonId)}/share`;

export type ShareLink = { schemaVersion: 1; shared: boolean; path: string | null; sharedAt: string | null };

const SHARED_PAGE = matching(/^\/shared\/(answers|lessons)\/[A-Za-z0-9_-]{22,64}$/, "a shared page path");

export const shareLinkShape: Shape<ShareLink> = object<ShareLink>({
  schemaVersion: oneOf([1] as const),
  shared: boolean,
  path: nullable(SHARED_PAGE),
  sharedAt: nullable(INSTANT)
});

export function checkedShareLink(link: ShareLink): ShareLink {
  if ((link.path !== null) !== link.shared || (link.sharedAt !== null) !== link.shared) {
    throw new ShapeError("shareLink", "a path and a time exactly while it is shared");
  }
  return link;
}

export async function fetchShareLink(sharePath: string): Promise<ShareLink> {
  return checkedShareLink(parseShape(shareLinkShape, await apiFetch<unknown>(sharePath)));
}

export async function startSharing(sharePath: string): Promise<ShareLink> {
  return checkedShareLink(parseShape(shareLinkShape, await apiFetch<unknown>(sharePath, { method: "PUT" })));
}

export async function stopSharing(sharePath: string): Promise<ShareLink> {
  await apiFetch<unknown>(sharePath, { method: "DELETE" });
  return NOT_SHARED;
}

export const NOT_SHARED: ShareLink = { schemaVersion: 1, shared: false, path: null, sharedAt: null };

export function sharedAddress(origin: string, link: ShareLink): string | null {
  return link.path ? `${origin}${link.path}` : null;
}

export async function fetchSharedAnswer(token: string): Promise<ExplainerVersionDocument> {
  return parseShape(explainerVersionDocumentShape, await apiFetch<unknown>(SHARED_ANSWER_PATH(token)));
}

export async function fetchReadingLanguages(): Promise<AnswerLanguage[]> {
  const body = await apiFetch<{ languages?: unknown }>(ANSWER_LANGUAGES_PATH);
  return answerLanguagesOf(body.languages);
}

export type SharedReading<T> = { body: T; languages: AnswerLanguage[] };

export async function withReadingLanguages<T>(read: Promise<T>, languages: () => Promise<AnswerLanguage[]> = fetchReadingLanguages): Promise<SharedReading<T>> {
  const listed = languages().catch((cause: unknown) => {
    console.error(cause);
    return answerLanguagesOf(null);
  });
  const [body, shown] = await Promise.all([read, listed]);
  return { body, languages: shown };
}

export async function fetchSharedLesson(token: string): Promise<LessonPack> {
  return parseShape(lessonPackShape, await apiFetch<unknown>(SHARED_LESSON_PATH(token)));
}
