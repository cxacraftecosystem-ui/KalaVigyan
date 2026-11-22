export type MoveDirection = "up" | "down";

export function moveItem<T>(list: readonly T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) return [...list];
  const next = [...list];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

export function usableAfterMove(from: number, to: number, count: number): MoveDirection {
  if (to === 0) return "down";
  if (to === count - 1) return "up";
  return to > from ? "down" : "up";
}

export function movedText(name: string, to: number, count: number): string {
  return `${name} moved to position ${to + 1} of ${count}.`;
}

export function inListedOrder<T extends { id: string }>(items: readonly T[], ids: readonly string[]): T[] {
  const byId = new Map(items.map((item) => [item.id, item]));
  const listed = ids.flatMap((id) => {
    const item = byId.get(id);
    return item ? [item] : [];
  });
  const kept = new Set(ids);
  return [...listed, ...items.filter((item) => !kept.has(item.id))];
}
