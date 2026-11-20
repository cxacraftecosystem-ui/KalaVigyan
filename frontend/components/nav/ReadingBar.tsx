"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { SignInLink } from "@/components/auth/SignInLink";
import { Appbar, type BarLink } from "@/components/nav/Appbar";
import { PublicNavLinks, publicLinks } from "@/components/nav/PublicNav";

export function ReadingBarView({ links, account }: { links: readonly BarLink[]; account: ReactNode }) {
  return (
    <Appbar brandHref="/">
      <PublicNavLinks links={links} />
      <div className="kv-bar-end" data-testid="reading-bar">
        {account}
      </div>
    </Appbar>
  );
}

export function ReadingBar({ signIn }: { signIn: boolean }) {
  const pathname = usePathname() ?? "/";
  return <ReadingBarView links={publicLinks(pathname)} account={signIn ? <SignInLink variant="quiet" /> : null} />;
}
