"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ClosedUploadLink } from "@/components/contributions/ClosedUploadLink";
import { LinkedPictureForm } from "@/components/contributions/LinkedPictureForm";
import { LinkedSlot } from "@/components/contributions/LinkedSlot";
import { failureMessage, useRemote, type Remote } from "@/components/hooks/useRemote";
import { PageHeader } from "@/components/PageHeader";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/Skeleton";
import { TextLink } from "@/components/ui/TextLink";
import { ApiError } from "@/lib/api";
import { sentNotice, type ImageContribution } from "@/lib/imageContributionContract";
import { fetchUploadLink, PICTURES_PATH, UPLOAD_LINK_PARAM, uploadLinkToken, uploadPageHref, type UploadLinkView } from "@/lib/uploadLinkContract";

const DESCRIPTION = "The craft and the facts were chosen when the link was made. Say what the picture is, confirm the declaration and add the file.";

export default function UploadLinkPage() {
  return (
    <Suspense fallback={<Header />}>
      <UploadLink />
    </Suspense>
  );
}

function Header() {
  return <PageHeader title="Give a picture" description={DESCRIPTION} />;
}

function UploadLink() {
  const params = useSearchParams();
  const router = useRouter();
  const token = uploadLinkToken(params.get(UPLOAD_LINK_PARAM));
  const load = useMemo(() => (token ? () => fetchUploadLink(token) : null), [token]);
  const link = useRemote(load);
  const [sent, setSent] = useState<ImageContribution | null>(null);

  return (
    <>
      <Header />
      <div className="grid max-w-measure gap-10">
        {token ? (
          <LinkBody token={token} link={link} sent={sent} onSent={setSent} onRenewed={(next) => router.replace(uploadPageHref(next))} />
        ) : (
          <Elsewhere line="This page opens from a picture link made for you in a chat. To give a picture without one, choose its craft and facts yourself." />
        )}
      </div>
    </>
  );
}

function LinkBody({
  token,
  link,
  sent,
  onSent,
  onRenewed
}: {
  token: string;
  link: Remote<UploadLinkView>;
  sent: ImageContribution | null;
  onSent: (sent: ImageContribution) => void;
  onRenewed: (token: string) => void;
}) {
  if (sent) return <Sent sent={sent} />;
  if (link.failure) {
    if (link.failure.cause instanceof ApiError && link.failure.cause.status === 404) {
      return <Elsewhere line="This link belongs to another account. Sign in with the account that asked for it, or give the picture here." />;
    }
    return <Retry message={failureMessage(link.failure, "Couldn't open the picture link.")} onRetry={link.retry} />;
  }
  if (!link.data) return <Skeleton shape="lede" label="Opening the picture link" />;
  if (link.data.state !== "OPEN") return <ClosedUploadLink token={token} view={link.data} onRenewed={onRenewed} />;
  return (
    <>
      <LinkedSlot view={link.data} />
      <LinkedPictureForm token={token} view={link.data} onSent={onSent} onClosed={link.retry} />
    </>
  );
}

function Sent({ sent }: { sent: ImageContribution }) {
  return (
    <section className="grid gap-3 border-t border-ink-1 pt-4" data-testid="linked-picture-sent">
      <p role="status" className="text-body-sm font-reading text-ink-1">
        {sentNotice(sent)}
      </p>
      <TextLink href={PICTURES_PATH} standalone>
        See your pictures
      </TextLink>
    </section>
  );
}

function Elsewhere({ line }: { line: string }) {
  return (
    <section className="grid gap-3 border-t border-ink-1 pt-4">
      <p className="text-body-sm font-reading text-ink-2">{line}</p>
      <TextLink href={PICTURES_PATH} standalone>
        Give a picture without a link
      </TextLink>
    </section>
  );
}

function Retry({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="grid gap-3 border-t border-ink-1 pt-4">
      <p role="alert" className="text-ui font-ui text-error">
        {message}
      </p>
      <ActionGroup align="start">
        <Button type="button" variant="quiet" onClick={onRetry}>
          Try again
        </Button>
      </ActionGroup>
    </section>
  );
}
