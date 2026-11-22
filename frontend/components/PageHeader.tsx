import type { ReactNode } from "react";

import { BackButton } from "@/components/BackButton";
import { ActionGroup } from "@/components/ui/ActionGroup";

export type PageHeaderProps = {
  title: string;
  description?: ReactNode;
  kicker?: string;
  actions?: ReactNode;
  back?: boolean;
};

export function PageHeader({ title, description, kicker, actions, back = true }: PageHeaderProps) {
  return (
    <header className="mb-10 grid gap-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
      <div className="grid min-w-0 justify-items-start gap-3">
        {back ? <BackButton /> : null}
        {kicker ? <p className="kicker">{kicker}</p> : null}
        <h1 className="max-w-full break-words font-headline text-h1 text-ink-1">{title}</h1>
        {description ? <p className="max-w-measure font-reading text-lede text-ink-2">{description}</p> : null}
      </div>
      {actions ? <ActionGroup align="end">{actions}</ActionGroup> : null}
    </header>
  );
}
