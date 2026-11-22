import { createContext, useContext, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export type FigureTexts = { kicker?: ReactNode; title?: ReactNode; dek?: ReactNode; source?: ReactNode };
export type FigureTable = { node: ReactNode; count: number };

type FigureProps = { texts: FigureTexts; table?: FigureTable | null; className?: string; children: ReactNode } & Omit<HTMLAttributes<HTMLElement>, "title" | "children" | "className">;

export function valuesLabel(count: number): string {
  return count === 1 ? "The value" : `All ${count} values`;
}

export const NumberedFigures = createContext(false);

function FigureNumber({ kicker }: { kicker?: ReactNode }) {
  const numbered = useContext(NumberedFigures);
  if (!numbered && !kicker) return null;
  return (
    <p className="kv-fig-no mb-0">
      {numbered ? <span className="kv-fig-count" data-testid="figure-number" /> : null}
      {numbered && kicker ? " · " : null}
      {kicker}
    </p>
  );
}

function FigureHead({ texts }: { texts: FigureTexts }) {
  if (!texts.kicker && !texts.title && !texts.dek) return null;
  return (
    <figcaption className="mb-3.5 grid min-w-0 gap-1.5">
      <FigureNumber kicker={texts.kicker} />
      {texts.title ? <p className="break-words font-reading text-h3 text-ink-1 [font-variant-numeric:lining-nums]">{texts.title}</p> : null}
      {texts.dek ? <p className="max-w-measure font-ui text-ui font-normal text-ink-2">{texts.dek}</p> : null}
    </figcaption>
  );
}

export function AnswerFigure({ texts, table = null, className, children, ...rest }: FigureProps) {
  return (
    <figure className={cn("kv-figure m-0 min-w-0", className)} {...rest}>
      <FigureHead texts={texts} />
      <div className="min-w-0">{children}</div>
      {texts.source ? <p className="mt-2.5 font-ui text-caption text-ink-3">{texts.source}</p> : null}
      {table ? (
        <details className="mt-2" data-testid="figure-values">
          <summary className="kv-link inline-flex min-h-target cursor-pointer items-center font-ui text-ui">{valuesLabel(table.count)}</summary>
          <div className="mt-2 overflow-x-auto">{table.node}</div>
        </details>
      ) : null}
    </figure>
  );
}
