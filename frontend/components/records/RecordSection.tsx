import { useId, type ReactNode, type Ref } from "react";

import { cn } from "@/lib/utils";

export type RecordSectionProps = {
  title: ReactNode;
  description?: ReactNode;
  aside?: ReactNode;
  children?: ReactNode;
  className?: string;
  testId?: string;
  ref?: Ref<HTMLElement>;
};

export function RecordSection({ title, description, aside, children, className, testId, ref }: RecordSectionProps) {
  const heading = useId();
  return (
    <section ref={ref} aria-labelledby={heading} className={cn("grid min-w-0 content-start gap-5 border-t border-rule pt-6", className)} data-testid={testId}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="grid min-w-0 max-w-measure gap-1.5">
          <h2 id={heading} className="font-headline text-h3 text-ink-1">
            {title}
          </h2>
          {description ? <p className="font-ui text-ui font-normal text-ink-2">{description}</p> : null}
        </div>
        {aside ? <div className="min-w-0 font-ui text-label text-ink-3">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}
