import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/Skeleton";

type GuideSectionProps = { id: string; title: string; about: string; ready: boolean; failed?: boolean; loading?: string; children: () => ReactNode };

export function GuideSection({ id, title, about, ready, failed = false, loading = "Reading the server", children }: GuideSectionProps) {
  if (!ready && failed) return null;
  const heading = `${id}-h`;
  return (
    <section id={id} aria-labelledby={heading} className="grid min-w-0 scroll-mt-24 content-start gap-6 border-t border-ink-1 pt-6" data-testid={`connect-${id}`}>
      <div className="grid max-w-measure gap-2">
        <h2 id={heading} className="font-headline text-h2 text-ink-1">
          {title}
        </h2>
        <p className="m-0 font-ui text-ui font-normal text-ink-2">{about}</p>
      </div>
      {ready ? children() : <Skeleton shape="lede" label={loading} />}
    </section>
  );
}
