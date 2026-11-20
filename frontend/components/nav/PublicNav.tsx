"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { BarLink } from "@/components/nav/Appbar";

export const ATLAS_CATEGORIES_HREF = "/crafts#atlas-index";

export const PUBLIC_LINKS = [
  { key: "atlas", href: "/crafts", label: "Atlas", section: "/crafts" },
  { key: "map", href: "/map", label: "Map", section: "/map" },
  { key: "categories", href: ATLAS_CATEGORIES_HREF, label: "Categories", section: "/categories" },
  { key: "compare", href: "/compare", label: "Compare", section: "/compare" }
] as const;

function within(pathname: string, section: string): boolean {
  return pathname === section || pathname.startsWith(`${section}/`);
}

export function publicLinks(pathname: string, categoriesHref: string = ATLAS_CATEGORIES_HREF): BarLink[] {
  return PUBLIC_LINKS.map((link) => ({ href: link.key === "categories" ? categoriesHref : link.href, label: link.label, current: within(pathname, link.section) }));
}

export function PublicNavLinks({ links }: { links: readonly BarLink[] }) {
  return (
    <nav className="kv-pnav" aria-label="Reading" data-testid="public-nav">
      {links.map((link) => (
        <Link key={link.label} href={link.href} className="kv-pnav-link" aria-current={link.current ? "page" : undefined}>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}

export function PublicNav({ categoriesHref }: { categoriesHref?: string }) {
  const pathname = usePathname() ?? "/";
  return <PublicNavLinks links={publicLinks(pathname, categoriesHref)} />;
}
