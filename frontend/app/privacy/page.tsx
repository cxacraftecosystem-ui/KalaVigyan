"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandLockup } from "@/components/BrandMark";
import { InstitutionFooter } from "@/components/landing/Footer";
import { Markdown } from "@/components/Markdown";
import { RetryPanel } from "@/components/RemotePanels";
import { SkipLink } from "@/components/shell/ShellFrame";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate } from "@/lib/format";
import { fetchPrivacyNotice, type PrivacyNotice } from "@/lib/signUp";

function Notice({ notice }: { notice: PrivacyNotice }) {
  return (
    <>
      <header className="grid gap-3 border-b border-rule pb-6">
        <p className="kicker">Privacy notice</p>
        <h1 className="font-headline text-h1 text-ink-1">{notice.title}</h1>
        <p className="font-ui text-label text-ink-3 lining-nums tabular-nums">
          Version {notice.version}
          {notice.publishedAt ? ` · published ${formatDate(notice.publishedAt)}` : ""}
        </p>
      </header>
      <Markdown text={notice.body} size="body" className="max-w-measure pt-6" />
    </>
  );
}

export default function PrivacyPage() {
  const [notice, setNotice] = useState<PrivacyNotice | null>(null);
  const [failed, setFailed] = useState(false);
  const [round, setRound] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    fetchPrivacyNotice()
      .then((next) => {
        if (!cancelled) setNotice(next);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [round]);

  return (
    <div className="kv-shell">
      <SkipLink />
      <main id="main-content" tabIndex={-1} className="kv-shell-main kv-shell-wrap">
        <Link href="/" className="mb-10 inline-flex rounded-control" aria-label="KalaVigyan home">
          <BrandLockup />
        </Link>
        <article className="mx-auto w-full max-w-[52rem]">
          {notice ? (
            <Notice notice={notice} />
          ) : failed ? (
            <RetryPanel message="Couldn't load the privacy notice. Check your connection and try again." onRetry={() => setRound((value) => value + 1)} />
          ) : (
            <Skeleton shape="lede" label="Opening the privacy notice" />
          )}
        </article>
      </main>
      <InstitutionFooter />
    </div>
  );
}
