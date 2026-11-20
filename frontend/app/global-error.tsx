"use client";

import { GlobalErrorView } from "@/components/GlobalErrorView";
import { PREFERENCES_BOOT_SCRIPT } from "@/lib/preferences";
import "./globals.css";

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <title>Something went wrong · KalaVigyan</title>
      </head>
      <body className="min-h-screen">
        <script dangerouslySetInnerHTML={{ __html: PREFERENCES_BOOT_SCRIPT }} />
        <GlobalErrorView reference={error.digest} />
      </body>
    </html>
  );
}
