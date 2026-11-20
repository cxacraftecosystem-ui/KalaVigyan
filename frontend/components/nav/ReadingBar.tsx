"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { SignInLink } from "@/components/auth/SignInLink";
import { Appbar, AppNav, currentHref, type BarLink } from "@/components/nav/Appbar";
import { MenuLinks, MenuSheet } from "@/components/nav/MenuSheet";

export const READING_LINKS = [
  { href: "/crafts", label: "Crafts" },
  { href: "/map", label: "Map" },
  { href: "/compare", label: "Compare" }
] as const;

export function ReadingBarView({ links, account }: { links: readonly BarLink[]; account: ReactNode }) {
  return (
    <Appbar brandHref="/">
      <div className="kv-bar-end" data-testid="reading-bar">
        <AppNav links={links} />
        {account ? <span className="contents max-md:hidden">{account}</span> : null}
        <MenuSheet>
          {(close) => (
            <>
              <MenuLinks entries={links} onNavigate={close} />
              {account ? (
                <div className="kv-menu-account" data-testid="menu-account">
                  <div className="grid px-3 pb-1">{account}</div>
                </div>
              ) : null}
            </>
          )}
        </MenuSheet>
      </div>
    </Appbar>
  );
}

export function ReadingBar({ signIn }: { signIn: boolean }) {
  const pathname = usePathname();
  const current = currentHref(READING_LINKS.map((link) => link.href), pathname);
  const links = READING_LINKS.map((link) => ({ href: link.href, label: link.label, current: link.href === current }));
  return <ReadingBarView links={links} account={signIn ? <SignInLink variant="quiet" /> : null} />;
}
