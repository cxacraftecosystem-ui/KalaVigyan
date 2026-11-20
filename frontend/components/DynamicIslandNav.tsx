"use client";

import { usePathname, useRouter } from "next/navigation";
import { useMemo } from "react";
import {
  BarChart3,
  Bookmark,
  BookOpen,
  BookPlus,
  ClipboardCheck,
  ImagePlus,
  KeyRound,
  MapPinned,
  MessageCircleQuestion,
  MessageSquareQuote,
  Mic,
  Plug,
  Presentation,
  Route,
  Settings as SettingsIcon,
  ShieldCheck,
  SlidersHorizontal,
  UserCog,
  type LucideIcon
} from "lucide-react";

import { useAdminView } from "@/components/AdminViewProvider";
import { useAuth } from "@/components/AuthProvider";
import { usePendingAccessCount } from "@/components/hooks/usePendingAccessCount";
import { useNotes } from "@/components/learn/useNotes";
import { AccountMenu, AccountPanel, type AccountView } from "@/components/nav/AccountMenu";
import { Appbar, AppNav, currentHref } from "@/components/nav/Appbar";
import { MenuGroup, MenuLinks, MenuSheet, type MenuEntry } from "@/components/nav/MenuSheet";
import { PendingAccessBadge, UnreadBadge } from "@/components/nav/navBadges";
import { CONNECT_PATH, CONNECT_TITLE } from "@/lib/connectClients";
import { canManageAccessRoster, hasAdminView, roleLabel, routeAllows } from "@/lib/permissions";
import { SAVED_PATH } from "@/lib/savedView";
import type { User } from "@/lib/types";

export const NAV_GROUPS = ["Tools", "Admin", "Account"] as const;
type NavGroup = (typeof NAV_GROUPS)[number];

export const PENDING_ACCESS_BADGE_HREF = "/admin/access";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  group: NavGroup | null;
  can: (user: User) => boolean;
  gate: string;
  adminSurface?: boolean;
};

const everyone = () => true;

export const NAV_ITEMS: NavItem[] = [
  { href: "/ask", label: "Ask", icon: MessageCircleQuestion, group: null, can: everyone, gate: "get_current_user" },
  { href: "/crafts", label: "Crafts", icon: BookOpen, group: null, can: everyone, gate: "get_current_user" },
  { href: "/map", label: "Map", icon: MapPinned, group: null, can: everyone, gate: "get_current_user" },
  { href: SAVED_PATH, label: "Saved", icon: Bookmark, group: null, can: everyone, gate: "get_current_user" },
  { href: "/lessons", label: "Lessons", icon: Presentation, group: "Tools", can: routeAllows("/lessons"), gate: "require(BUILD_LESSONS)" },
  { href: "/contribute", label: "Contribute", icon: Mic, group: "Tools", can: routeAllows("/contribute"), gate: "require(CONTRIBUTE_TESTIMONY)" },
  { href: "/contributions/pictures", label: "Give a picture", icon: ImagePlus, group: "Tools", can: routeAllows("/contributions/pictures"), gate: "require(PROPOSE_KNOWLEDGE)" },
  { href: "/contributions/facts", label: "Propose knowledge", icon: BookPlus, group: "Tools", can: routeAllows("/contributions/facts"), gate: "require(PROPOSE_KNOWLEDGE)" },

  { href: "/admin", label: "Settings hub", icon: SlidersHorizontal, group: "Admin", can: routeAllows("/admin"), gate: "require_admin", adminSurface: true },
  { href: "/admin/access", label: "Who may sign in", icon: ShieldCheck, group: "Admin", can: routeAllows("/admin/access"), gate: "require_access_roster_manager", adminSurface: true },
  { href: "/admin/users", label: "Manage users", icon: UserCog, group: "Admin", can: routeAllows("/admin/users"), gate: "require_professor", adminSurface: true },
  { href: "/admin/review", label: "Review", icon: ClipboardCheck, group: "Admin", can: routeAllows("/admin/review"), gate: "queue_reviewer", adminSurface: true },
  { href: "/admin/pictures", label: "Contributed pictures", icon: ImagePlus, group: "Admin", can: routeAllows("/admin/pictures"), gate: "require(REVIEW_CONTRIBUTIONS)", adminSurface: true },
  { href: "/admin/testimony", label: "Artisan testimony", icon: MessageSquareQuote, group: "Admin", can: routeAllows("/admin/testimony"), gate: "require(REVIEW_TESTIMONY)", adminSurface: true },
  { href: "/admin/keys", label: "API keys", icon: KeyRound, group: "Admin", can: routeAllows("/admin/keys"), gate: "require_master_admin", adminSurface: true },
  { href: "/admin/routing", label: "AI routing", icon: Route, group: "Admin", can: routeAllows("/admin/routing"), gate: "require_master_admin", adminSurface: true },
  { href: "/admin/usage", label: "Usage", icon: BarChart3, group: "Admin", can: routeAllows("/admin/usage"), gate: "require_view_usage", adminSurface: true },

  { href: CONNECT_PATH, label: CONNECT_TITLE, icon: Plug, group: "Account", can: everyone, gate: "get_current_user" },
  { href: "/settings", label: "Settings", icon: SettingsIcon, group: "Account", can: everyone, gate: "get_current_user" }
];

export function isNavItemVisible(item: NavItem, user: User | null | undefined, adminMode: boolean): boolean {
  if (!user || !item.can(user)) return false;
  if (item.adminSurface && hasAdminView(user)) return adminMode;
  return true;
}

export type NavCounts = { pendingAccess: number; unreadNotes: number };

export function navEntry(item: NavItem, current: string | null, counts: NavCounts): MenuEntry {
  const Icon = item.icon;
  const badge = item.href === PENDING_ACCESS_BADGE_HREF ? <PendingAccessBadge count={counts.pendingAccess} /> : item.href === SAVED_PATH ? <UnreadBadge count={counts.unreadNotes} /> : null;
  return { href: item.href, label: item.label, current: item.href.split("?")[0] === current, icon: <Icon aria-hidden />, badge };
}

function GroupedEntries({ groups, onNavigate }: { groups: readonly { label: string; entries: MenuEntry[] }[]; onNavigate: () => void }) {
  return (
    <>
      {groups.map((group) => (
        <MenuGroup key={group.label} label={group.label}>
          <MenuLinks entries={group.entries} onNavigate={onNavigate} />
        </MenuGroup>
      ))}
    </>
  );
}

function useNavModel(user: User | null, adminMode: boolean, pathname: string) {
  const visible = useMemo(() => NAV_ITEMS.filter((item) => isNavItemVisible(item, user, adminMode)), [user, adminMode]);
  const rosterShown = visible.some((item) => item.href === PENDING_ACCESS_BADGE_HREF);
  const pendingAccess = usePendingAccessCount(rosterShown && canManageAccessRoster(user))?.pending ?? 0;
  const unreadNotes = useNotes(user?.id ?? null).list?.unread ?? 0;
  const counts: NavCounts = { pendingAccess, unreadNotes };
  const current = currentHref(visible.map((item) => item.href), pathname);
  const roots = visible.filter((item) => item.group === null).map((item) => navEntry(item, current, counts));
  const groups = NAV_GROUPS.map((label) => ({ label, entries: visible.filter((item) => item.group === label).map((item) => navEntry(item, current, counts)) })).filter((group) => group.entries.length > 0);
  return { roots, groups, pendingAccess };
}

export function DynamicIslandNav() {
  const { user, logout } = useAuth();
  const { adminMode, available, toggleAdminView } = useAdminView();
  const router = useRouter();
  const pathname = usePathname();
  const { roots, groups, pendingAccess } = useNavModel(user, adminMode, pathname);

  if (!user) return null;

  const account: AccountView = {
    name: user.name,
    role: roleLabel(user.role),
    adminToggle: available ? { checked: adminMode, onChange: toggleAdminView } : null,
    onSignOut: () => {
      void logout().then(
        () => router.replace("/login"),
        () => undefined
      );
    }
  };

  return (
    <Appbar brandHref="/ask">
      <div className="kv-bar-end">
        <AppNav links={roots}>
          <AccountMenu count={pendingAccess}>
            {(close) => (
              <AccountPanel account={account}>
                <GroupedEntries groups={groups} onNavigate={close} />
              </AccountPanel>
            )}
          </AccountMenu>
        </AppNav>
        <MenuSheet count={pendingAccess}>
          {(close) => (
            <>
              <MenuLinks entries={roots} onNavigate={close} />
              <GroupedEntries groups={groups} onNavigate={close} />
              <AccountPanel account={account} />
            </>
          )}
        </MenuSheet>
      </div>
    </Appbar>
  );
}
