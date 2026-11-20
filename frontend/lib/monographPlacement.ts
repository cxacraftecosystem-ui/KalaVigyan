import type { MonographDocument } from "@/lib/monographDocument";

export const PAGE_LAYOUT_DATA = "page-layout";
export const MASTHEAD_ROLES: readonly string[] = ["HERO", "OPENER"];
const PICTURE_KIND = "picture_plate";

type Placed = { ref: string; chapter: string; role: string; order: number };

function placedEntries(value: unknown): Placed[] {
  const entries = value && typeof value === "object" ? (value as { entries?: unknown }).entries : null;
  if (!Array.isArray(entries)) return [];
  return entries.flatMap((entry) => {
    if (!entry || typeof entry !== "object") return [];
    const { ref, chapter, role, order } = entry as Record<string, unknown>;
    if (typeof ref !== "string" || typeof chapter !== "string" || typeof role !== "string") return [];
    return [{ ref, chapter, role, order: typeof order === "number" ? order : 0 }];
  });
}

export function placedMastheadPicture(document: MonographDocument): string | null {
  const pictures = new Set(document.content.components.filter((component) => component.kind === PICTURE_KIND).map((component) => component.label));
  const chapters = [...new Set(document.content.layout.map((entry) => entry.chapter))];
  const rank = (placed: Placed) => [MASTHEAD_ROLES.indexOf(placed.role), chapters.indexOf(placed.chapter), placed.order];
  const found = placedEntries(document.content.data[PAGE_LAYOUT_DATA])
    .filter((placed) => pictures.has(placed.ref) && MASTHEAD_ROLES.includes(placed.role) && chapters.includes(placed.chapter))
    .sort((a, b) => {
      const [left, right] = [rank(a), rank(b)];
      return left[0] - right[0] || left[1] - right[1] || left[2] - right[2];
    });
  return found[0]?.ref ?? null;
}
