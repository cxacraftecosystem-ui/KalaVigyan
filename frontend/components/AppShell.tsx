"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Lock } from "lucide-react";

import {
  adminChromeRouteFor,
  adminChromeVisible,
  useAdminView,
  type AdminChromeRoute
} from "@/components/AdminViewProvider";
import { useAuth } from "@/components/AuthProvider";
import { DeadEndFrame, ErrorState } from "@/components/DeadEnd";
import { DynamicIslandNav } from "@/components/DynamicIslandNav";
import { ErrorPanel } from "@/components/ErrorPanel";
import { Appbar } from "@/components/nav/Appbar";
import { AccountGate } from "@/components/shell/AccountGate";
import { ShellFrame } from "@/components/shell/ShellFrame";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button, buttonLook } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/Skeleton";
import { CONNECT_PATH } from "@/lib/connectClients";
import { browserOffline } from "@/lib/errorKind";
import { hasAdminView, routeGuardFor } from "@/lib/permissions";
import { signInHref } from "@/lib/sessionReturn";
import type { User } from "@/lib/types";

export const FIRST_PAINT_PATHS: readonly string[] = ["/ask", CONNECT_PATH];

export function drawsBeforeAccount(pathname: string | null): boolean {
  return FIRST_PAINT_PATHS.includes(pathname ?? "");
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, reach, retryMe } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user && reach === "ok") router.replace(signInHref(`${window.location.pathname}${window.location.search}`));
  }, [loading, reach, router, user]);

  if (loading) {
    return (
      <ShellFrame nav={<Appbar brandHref="/ask" />} onRetry={null}>
        {drawsBeforeAccount(pathname) ? children : <Skeleton shape="lede" label="Opening your account" />}
      </ShellFrame>
    );
  }

  if (!user && reach === "retrying") return <Unreachable onRetry={retryMe} />;

  if (!user) return null;

  return (
    <AccountGate user={user}>
      <ShellFrame nav={<DynamicIslandNav />} onRetry={reach === "retrying" ? retryMe : null}>
        <GuardedRoute user={user}>{children}</GuardedRoute>
      </ShellFrame>
    </AccountGate>
  );
}

function GuardedRoute({ user, children }: { user: User; children: React.ReactNode }) {
  const { adminMode, adminViewResolved, setAdminView } = useAdminView();
  const pathname = usePathname();
  const guard = routeGuardFor(pathname);
  if (guard && !guard.can(user)) return <RouteLocked title={guard.title} message={guard.message} />;
  const chrome = adminChromeRouteFor(pathname);
  if (chrome && hasAdminView(user) && !adminViewResolved) return <Skeleton shape="lede" label="Checking your admin view" />;
  if (chrome && !adminChromeVisible(user, adminMode)) return <AdminViewHidden route={chrome} onEnable={() => setAdminView(true)} />;
  return <>{children}</>;
}

function Unreachable({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" data-testid="unreachable">
      <DeadEndFrame nav={false}>
        <ErrorState kind={browserOffline() ? "offline" : "unavailable"} onRetry={onRetry} />
      </DeadEndFrame>
    </div>
  );
}

function RouteLocked({ title, message }: { title: string; message: string }) {
  return (
    <ErrorPanel screen="forbidden" tone="notice" icon={<Lock className="h-5 w-5" aria-hidden />} title={title} line={message}>
      <Link href="/ask" {...buttonLook({ variant: "primary" })}>
        Home
      </Link>
    </ErrorPanel>
  );
}

function AdminViewHidden({ route, onEnable }: { route: AdminChromeRoute; onEnable: () => void }) {
  return (
    <section className="kv-empty mx-auto max-w-2xl" aria-live="polite">
      <h1 className="font-headline text-h2 text-ink-1">{route.label} is hidden while admin view is off</h1>
      <p className="max-w-measure font-reading text-body text-ink-2">{route.blurb} Turn admin view on to open it.</p>
      <ActionGroup className="mt-3">
        <Button variant="primary" onClick={onEnable}>
          Turn admin view back on
        </Button>
        {route.alternative ? (
          <Link href={route.alternative.href} {...buttonLook({ variant: "quiet" })}>
            {route.alternative.label}
          </Link>
        ) : null}
        <Link href="/ask" {...buttonLook({ variant: "quiet" })}>
          Home
        </Link>
      </ActionGroup>
    </section>
  );
}
