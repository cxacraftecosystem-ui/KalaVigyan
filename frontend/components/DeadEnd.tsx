"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { KeyRound, Lock, SearchX, ServerOff, TriangleAlert, WifiOff } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { DynamicIslandNav } from "@/components/DynamicIslandNav";
import { ErrorBrand, ErrorPanel, type ErrorTone } from "@/components/ErrorPanel";
import { SkipLink } from "@/components/shell/ShellFrame";
import { Button, buttonLook } from "@/components/ui/button";
import { errorCopy, errorKindOf, retryDelaySeconds, type ErrorKind } from "@/lib/errorKind";
import { signInHref } from "@/lib/sessionReturn";

export function DeadEndFrame({ nav, children }: { nav: boolean; children: ReactNode }) {
  const { user, loading } = useAuth();

  const brand = !nav || (!loading && !user);

  return (
    <div className="kv-shell">
      {nav ? (
        <>
          <SkipLink />
          <DynamicIslandNav />
        </>
      ) : null}
      <main id="main-content" tabIndex={-1} className="kv-shell-main kv-shell-wrap">
        {brand ? <ErrorBrand /> : null}
        {children}
      </main>
    </div>
  );
}

const ICON: Record<ErrorKind, ReactNode> = {
  "not-found": <SearchX className="h-5 w-5" aria-hidden />,
  forbidden: <Lock className="h-5 w-5" aria-hidden />,
  session: <KeyRound className="h-5 w-5" aria-hidden />,
  server: <TriangleAlert className="h-5 w-5" aria-hidden />,
  offline: <WifiOff className="h-5 w-5" aria-hidden />,
  unavailable: <ServerOff className="h-5 w-5" aria-hidden />
};

const TONE: Record<ErrorKind, ErrorTone> = {
  "not-found": "notice",
  forbidden: "notice",
  session: "notice",
  server: "alert",
  offline: "quiet",
  unavailable: "quiet"
};

const PRIMARY = buttonLook({ variant: "primary" });
const QUIET = buttonLook({ variant: "quiet" });

function useHere(): string | null {
  const [here, setHere] = useState<string | null>(null);
  useEffect(() => {
    setHere(`${window.location.pathname}${window.location.search}${window.location.hash}`);
  }, []);
  return here;
}

function useCountdown(active: boolean, onDone: () => void): number | null {
  const [round, setRound] = useState(0);
  const [left, setLeft] = useState<number | null>(null);
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  });
  useEffect(() => {
    if (!active) {
      setLeft(null);
      return;
    }
    const total = retryDelaySeconds(round);
    const started = Date.now();
    setLeft(total);
    const timer = window.setInterval(() => {
      const remaining = total - Math.floor((Date.now() - started) / 1000);
      if (remaining > 0) {
        setLeft(remaining);
        return;
      }
      window.clearInterval(timer);
      setRound((value) => value + 1);
      done.current();
    }, 250);
    return () => window.clearInterval(timer);
  }, [active, round]);
  return left;
}

type Ways = { home: string; requestHref?: string | null; signIn: string; goBack: () => void; retry: () => void };

function errorActions(kind: ErrorKind, ways: Ways): ReactNode {
  switch (kind) {
    case "not-found":
      return (
        <>
          <Button type="button" variant="quiet" onClick={ways.goBack}>
            Go back
          </Button>
          <Link href={ways.home} {...PRIMARY}>
            Home
          </Link>
        </>
      );
    case "forbidden":
      return ways.requestHref ? (
        <Link href={ways.requestHref} {...PRIMARY}>
          Request access
        </Link>
      ) : (
        <Link href={ways.home} {...PRIMARY}>
          Home
        </Link>
      );
    case "session":
      return (
        <Link href={ways.signIn} {...PRIMARY}>
          Sign in again
        </Link>
      );
    case "server":
      return (
        <>
          <Button type="button" variant="primary" onClick={ways.retry}>
            Try again
          </Button>
          <Link href={ways.home} {...QUIET}>
            Home
          </Link>
        </>
      );
    default:
      return (
        <Button type="button" variant="primary" onClick={ways.retry}>
          Try again
        </Button>
      );
  }
}

function Countdown({ seconds }: { seconds: number }) {
  return (
    <span data-testid="error-countdown">
      Retrying in <span className="font-code tabular-nums">{seconds}s</span>
    </span>
  );
}

export function ErrorState({
  kind,
  noun,
  requestHref,
  reference,
  onRetry,
  next
}: {
  kind: ErrorKind;
  noun?: string;
  requestHref?: string | null;
  reference?: string | null;
  onRetry?: () => void;
  next?: string | null;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const here = useHere();
  const home = loading || user ? "/ask" : "/";

  const retry = useCallback(() => {
    if (onRetry) onRetry();
    else window.location.reload();
  }, [onRetry]);

  useEffect(() => {
    if (kind !== "offline") return;
    window.addEventListener("online", retry);
    return () => window.removeEventListener("online", retry);
  }, [kind, retry]);

  const seconds = useCountdown(kind === "unavailable", retry);
  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push(home);
  };
  const copy = errorCopy(kind, { noun, canRequest: Boolean(requestHref) });
  const ways: Ways = { home, requestHref, signIn: signInHref(next ?? here), goBack, retry };

  return (
    <ErrorPanel
      screen={kind}
      icon={ICON[kind]}
      tone={TONE[kind]}
      title={copy.title}
      line={copy.line}
      reference={kind === "server" ? reference : null}
      status={kind === "unavailable" && seconds !== null ? <Countdown seconds={seconds} /> : null}
    >
      {errorActions(kind, ways)}
    </ErrorPanel>
  );
}

export function ApiErrorState({
  error,
  noun,
  requestHref,
  onRetry
}: {
  error: unknown;
  noun?: string;
  requestHref?: string | null;
  onRetry?: () => void;
}) {
  return <ErrorState kind={errorKindOf(error)} noun={noun} requestHref={requestHref} onRetry={onRetry} />;
}
