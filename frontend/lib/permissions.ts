import type { User, UserRole } from "@/lib/types";

export const ROLE_RANK: Record<UserRole, number> = {
  STUDENT: 15,
  ARTISAN: 18,
  RESEARCHER: 30,
  PROFESSOR: 40,
  ADMIN: 50,
  MASTER_ADMIN: 60
};

export const ROLE_LABELS: Record<UserRole, string> = {
  STUDENT: "Student",
  ARTISAN: "Artisan",
  RESEARCHER: "Researcher",
  PROFESSOR: "Professor",
  ADMIN: "Admin",
  MASTER_ADMIN: "Master Admin"
};

export const ROLES_BY_RANK: UserRole[] = (Object.keys(ROLE_RANK) as UserRole[]).sort(
  (a, b) => ROLE_RANK[b] - ROLE_RANK[a]
);

export function roleRank(userOrRole: User | UserRole | null | undefined): number {
  if (!userOrRole) return 0;
  const role = typeof userOrRole === "string" ? userOrRole : userOrRole.role;
  return ROLE_RANK[role] ?? 0;
}

export function roleLabel(role: string | null | undefined): string {
  return ROLE_LABELS[role as UserRole] ?? String(role ?? "");
}

export function hasRank(user: User | null | undefined, role: UserRole): boolean {
  return roleRank(user) >= ROLE_RANK[role];
}

export function isMasterAdmin(user: User | null | undefined) {
  return user?.role === "MASTER_ADMIN";
}

export function hasAdminView(user: User | null | undefined) {
  return isMasterAdmin(user);
}

export function assignableRoles(user: User | null | undefined): UserRole[] {
  if (isMasterAdmin(user)) return ROLES_BY_RANK;
  if (!canManageAccessRoster(user)) return [];
  const own = roleRank(user);
  return ROLES_BY_RANK.filter((role) => ROLE_RANK[role] < own);
}

export function canManageUser(user: User | null | undefined, target: User): boolean {
  if (isMasterAdmin(user)) return target.role !== "MASTER_ADMIN" || target.id === user?.id;
  return roleRank(target) < roleRank(user);
}

export function canManageUsers(user: User | null | undefined) {
  return hasRank(user, "PROFESSOR");
}

export function canChangeRoles(user: User | null | undefined) {
  return hasRank(user, "ADMIN");
}

export function canSuspendUsers(user: User | null | undefined) {
  return hasRank(user, "ADMIN");
}

export function canManageAccessRoster(user: User | null | undefined) {
  return hasRank(user, "PROFESSOR");
}

export function canManageAccessEntry(user: User | null | undefined, admitRole: UserRole | null): boolean {
  if (!canManageAccessRoster(user)) return false;
  return isMasterAdmin(user) || roleRank(admitRole) < roleRank(user);
}

export function canShareMedia(user: User | null | undefined) {
  return hasRank(user, "PROFESSOR");
}

export function canHideGenerated(user: User | null | undefined) {
  return hasRank(user, "PROFESSOR");
}

export function canBuildLessons(user: User | null | undefined) {
  return hasRank(user, "PROFESSOR");
}

export function canContributeTestimony(user: User | null | undefined) {
  return Boolean(user?.capabilities?.includes("CONTRIBUTE_TESTIMONY"));
}

export function canContributeImages(user: User | null | undefined) {
  return Boolean(user?.capabilities?.includes("PROPOSE_KNOWLEDGE"));
}

export function canReviewContributions(user: User | null | undefined) {
  return Boolean(user?.capabilities?.includes("REVIEW_CONTRIBUTIONS"));
}

export function canReviewTestimony(user: User | null | undefined) {
  return hasRank(user, "PROFESSOR");
}

export function canConfirmGuardianConsent(user: User | null | undefined) {
  return hasRank(user, "PROFESSOR");
}

export function canSaveExport(user: User | null | undefined) {
  return hasRank(user, "STUDENT");
}

export function canManageSecrets(user: User | null | undefined) {
  return isMasterAdmin(user);
}

export function canManageRouting(user: User | null | undefined) {
  return isMasterAdmin(user);
}

export function canReadUsage(user: User | null | undefined) {
  return hasRank(user, "ADMIN");
}

export function canOpenSettingsHub(user: User | null | undefined) {
  return hasRank(user, "ADMIN");
}

export type RouteGuard = {
  path: string;
  can: (user: User | null | undefined) => boolean;
  gate: string;
  title: string;
  message: string;
};

const MASTER_ADMIN_GUARD = {
  can: isMasterAdmin,
  gate: "require_master_admin",
  title: "Master admin access required",
  message: "Master admins only."
} as const;

const ADMIN_GUARD = {
  can: canOpenSettingsHub,
  gate: "require_admin",
  title: "Admin access required",
  message: "Needs Admin access or above."
} as const;

const PROFESSOR_GUARD = {
  can: canManageUsers,
  gate: "require_professor",
  title: "Professor access required",
  message: "Needs Professor access or above."
} as const;

export const ROUTE_GUARDS: RouteGuard[] = [
  { path: "/admin", ...ADMIN_GUARD },
  { path: "/admin/keys", ...MASTER_ADMIN_GUARD },
  { path: "/admin/routing", ...MASTER_ADMIN_GUARD },
  { path: "/admin/budget", ...MASTER_ADMIN_GUARD, gate: "require(MANAGE_CEILINGS)" },
  { path: "/admin/usage", ...ADMIN_GUARD, can: canReadUsage, gate: "require_view_usage" },
  { path: "/admin/users", ...PROFESSOR_GUARD },
  { path: "/admin/access", ...PROFESSOR_GUARD, gate: "require_access_roster_manager" },
  { path: "/admin/testimony", ...PROFESSOR_GUARD, can: canReviewTestimony, gate: "require(REVIEW_TESTIMONY)" },
  { path: "/admin/pictures", ...ADMIN_GUARD, can: canReviewContributions, gate: "require(REVIEW_CONTRIBUTIONS)" },
  { path: "/admin/field-photos", ...ADMIN_GUARD, can: canReviewContributions, gate: "require(REVIEW_CONTRIBUTIONS)" },
  { path: "/admin/review", ...PROFESSOR_GUARD, can: canReviewTestimony, gate: "queue_reviewer" },
  { path: "/contributions/pictures", can: canContributeImages, gate: "require(PROPOSE_KNOWLEDGE)", title: "For researchers and above", message: "Needs Researcher access or above." },
  { path: "/contributions/facts", can: canContributeImages, gate: "require(PROPOSE_KNOWLEDGE)", title: "For researchers and above", message: "Needs Researcher access or above." },
  { path: "/contributions/components", can: canContributeImages, gate: "require(PROPOSE_KNOWLEDGE)", title: "For researchers and above", message: "Needs Researcher access or above." },
  { path: "/contributions/translations", can: canContributeImages, gate: "require(PROPOSE_KNOWLEDGE)", title: "For researchers and above", message: "Needs Researcher access or above." },
  { path: "/contribute", can: canContributeTestimony, gate: "require(CONTRIBUTE_TESTIMONY)", title: "For artisans", message: "Artisan accounts only." },
  { path: "/lessons", ...PROFESSOR_GUARD, can: canBuildLessons, gate: "require(BUILD_LESSONS)" }
];

function routeMatches(rulePath: string, pathname: string): boolean {
  const rule = rulePath.split("/").filter(Boolean);
  const actual = pathname.split("/").filter(Boolean);
  if (actual.length < rule.length) return false;
  return rule.every((segment, index) => segment.startsWith(":") || segment === actual[index]);
}

export function routeGuardFor(pathname: string): RouteGuard | null {
  let best: RouteGuard | null = null;
  for (const guard of ROUTE_GUARDS) {
    if (!routeMatches(guard.path, pathname)) continue;
    if (!best || guard.path.length > best.path.length) best = guard;
  }
  return best;
}

export function canAccessRoute(user: User | null | undefined, pathname: string): boolean {
  const guard = routeGuardFor(pathname);
  return !guard || guard.can(user);
}

export function routeAllows(pathname: string): (user: User | null | undefined) => boolean {
  return (user) => canAccessRoute(user, pathname);
}
