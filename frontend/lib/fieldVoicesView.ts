import { scriptOf } from "@/lib/answerLanguages";
import type { FieldVoicesList, PageFieldPhoto, PageVoice } from "@/lib/fieldVoicesContract";

export const FIRST_QUOTES = 6;
export const FIRST_PHOTOS = 12;
export const MACHINE_TRANSLATION = "Machine translation";
export const VOICES_HEADING = "In the artisan's words";
export const GALLERY_HEADING = "From the workshops";
export const FULL_INTERVIEW = "Read the full interview";
export const SHOW_FEWER = "Show fewer";

const NASTALIQ_LANGUAGES: ReadonlySet<string> = new Set(["ur", "ks"]);
const LATIN = "Latn";

export type FieldVoicesFirst = { quotes: FieldVoicesList; images: FieldVoicesList };
export type FieldListPage = (cursor: string) => Promise<FieldVoicesList>;
export type PhotoGroupView = { key: string; label: string; photos: PageFieldPhoto[] };

export function hasFieldVoices(first: FieldVoicesFirst | null): first is FieldVoicesFirst {
  return first !== null && first.quotes.total + first.images.total > 0;
}

export function quotesOf(list: FieldVoicesList): PageVoice[] {
  return list.quotes;
}

export function photosOf(list: FieldVoicesList): PageFieldPhoto[] {
  return list.images;
}

export function showAllLabel(total: number): string {
  return `Show all ${total}`;
}

export function interviewPath(recordingId: string): string {
  return `/voices/${encodeURIComponent(recordingId)}`;
}

export function voiceScript(text: string, language: string): string | undefined {
  const script = scriptOf(text);
  if (!script || script === LATIN) return undefined;
  return script === "Arab" && NASTALIQ_LANGUAGES.has(language.split("-")[0]) ? "Aran" : script;
}

export async function restOfList<T>(cursor: string, page: FieldListPage, pick: (list: FieldVoicesList) => T[]): Promise<T[]> {
  const items: T[] = [];
  let next: string | null = cursor;
  while (next !== null) {
    const list = await page(next);
    items.push(...pick(list));
    if (list.nextCursor === next) throw new Error(`the field voices list does not move past cursor ${next}`);
    next = list.nextCursor;
  }
  return items;
}

export function photoGroups(photos: readonly PageFieldPhoto[]): PhotoGroupView[] {
  const groups = new Map<string, PhotoGroupView>();
  for (const photo of photos) {
    const [first] = photo.groups;
    const key = `${first.kind}:${first.key}`;
    const group = groups.get(key) ?? { key, label: first.label, photos: [] };
    group.photos.push(photo);
    groups.set(key, group);
  }
  return [...groups.values()];
}

export function photoCaption(photo: PageFieldPhoto): string {
  return photo.caption ?? photo.groups[0].label;
}

export function rightsLine(photo: PageFieldPhoto): string {
  return `${photo.statement} Rights holder: ${photo.rightsHolder}.`;
}
