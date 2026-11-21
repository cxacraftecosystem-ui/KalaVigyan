export const READING_ROUTES = ["/crafts", "/categories", "/map", "/compare", "/data", "/voices", "/shared"] as const;

export function isReadingRoute(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "") || "/";
  return READING_ROUTES.some((route) => path === route || path.startsWith(`${route}/`));
}
