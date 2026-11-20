import Link from "next/link";
import type { ReactNode } from "react";

import { AppbarLockup } from "@/components/BrandMark";
import { cn } from "@/lib/utils";

export type AppbarTone = "page" | "photo";

export type AppbarBrand = "full" | "compact";

export type BarLink = { href: string; label: string; current: boolean; badge?: ReactNode };

function Lockup({ brand }: { brand: AppbarBrand }) {
  if (brand === "full") return <AppbarLockup />;
  return (
    <>
      <span className="inline-flex sm:hidden">
        <AppbarLockup script="latin" />
      </span>
      <span className="inline-flex max-sm:hidden">
        <AppbarLockup />
      </span>
    </>
  );
}

export function Appbar({ brandHref, tone = "page", brand = "full", overlay = false, children }: { brandHref: string; tone?: AppbarTone; brand?: AppbarBrand; overlay?: boolean; children?: ReactNode }) {
  const photo = tone === "photo";
  return (
    <header className={cn("kv-bar", photo && "kv-on-photo")} data-tone={photo ? "photo" : undefined} data-overlay={overlay ? "" : undefined} data-testid="appbar">
      <div className="kv-shell-wrap kv-bar-in flex-wrap">
        <Link href={brandHref} className="kv-bar-brand">
          <Lockup brand={brand} />
        </Link>
        {children}
      </div>
    </header>
  );
}

export function AppNav({ links, label = "Main", children }: { links: readonly BarLink[]; label?: string; children?: ReactNode }) {
  return (
    <nav className="kv-bar-nav" aria-label={label}>
      {links.map((link) => (
        <Link key={link.href} href={link.href} className="kv-bar-link" aria-current={link.current ? "page" : undefined}>
          {link.label}
          {link.badge}
        </Link>
      ))}
      {children}
    </nav>
  );
}

export function currentHref(hrefs: readonly string[], pathname: string): string | null {
  let found: string | null = null;
  for (const href of hrefs) {
    const base = href.split("?")[0];
    if (pathname !== base && !pathname.startsWith(`${base}/`)) continue;
    if (!found || base.length > found.length) found = base;
  }
  return found;
}
