import { useId, type ReactNode } from "react";

import { BrandLockup } from "@/components/BrandMark";
import { ActionGroup } from "@/components/ui/ActionGroup";
import type { ErrorScreen } from "@/lib/errorKind";

export type ErrorTone = "alert" | "notice" | "quiet";

const TONE: Record<ErrorTone, string> = {
  alert: "bg-error-wash text-error",
  notice: "bg-info-wash text-info",
  quiet: "bg-sunk text-ink-2"
};

export function ErrorPanel({
  screen,
  icon,
  tone,
  title,
  line,
  status,
  reference,
  children
}: {
  screen: ErrorScreen;
  icon: ReactNode;
  tone: ErrorTone;
  title: string;
  line: string;
  status?: ReactNode;
  reference?: string | null;
  children?: ReactNode;
}) {
  const heading = useId();
  return (
    <section aria-labelledby={heading} data-testid={`error-${screen}`} className="mx-auto grid w-full max-w-xl justify-items-center border-y border-rule px-4 py-12 text-center sm:px-8 sm:py-14">
      <div className={`mb-5 grid h-12 w-12 place-items-center rounded-full ${TONE[tone]}`}>{icon}</div>
      <h1 id={heading} className="font-headline text-h2 text-ink-1 [overflow-wrap:anywhere]">
        {title}
      </h1>
      <p className="mt-3 max-w-[44ch] font-ui text-ui-lg text-ink-2">{line}</p>
      {status ? <div className="mt-2 font-ui text-ui text-ink-2">{status}</div> : null}
      {children ? <ActionGroup className="mt-7 w-full">{children}</ActionGroup> : null}
      {reference ? (
        <p className="mt-6 font-ui text-caption text-ink-3" data-testid="error-reference">
          Ref <code className="break-all font-code text-ink-2">{reference}</code>
        </p>
      ) : null}
    </section>
  );
}

export function ErrorBrand() {
  return (
    <div className="mb-8 flex justify-center" data-testid="error-brand">
      <BrandLockup />
    </div>
  );
}
