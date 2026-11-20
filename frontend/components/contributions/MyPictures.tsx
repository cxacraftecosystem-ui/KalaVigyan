"use client";

import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { HeldReasons } from "@/components/contributions/HeldReasons";
import { canWithdraw, heldReasons, IMAGE_STATUS_LABELS, type ImageContribution } from "@/lib/imageContributionContract";

export function MyPictures({
  items,
  busy,
  onWithdraw
}: {
  items: ImageContribution[];
  busy: boolean;
  onWithdraw: (item: ImageContribution) => void;
}) {
  if (!items.length) {
    return <p className="text-body-sm font-reading text-ink-2">Pictures you give appear here with what happened to each.</p>;
  }
  return (
    <ul className="grid gap-4" data-testid="my-pictures">
      {items.map((item) => (
        <li key={item.id} className="grid gap-3 border-t border-rule pt-4 sm:grid-cols-[160px_1fr]">
          {item.fileUrl ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element -- presigned bucket link, nothing for next/image to optimise */}
              <img src={item.fileUrl} alt={item.altText} className="aspect-[4/3] w-full rounded-plate bg-sunk object-cover" loading="lazy" />
            </>
          ) : (
            <div className="aspect-[4/3] w-full rounded-plate bg-sunk" aria-hidden />
          )}
          <div className="grid content-start gap-1">
            <p className="kicker">{item.craftName} · {item.label}</p>
            <p className="text-body-sm font-reading text-ink-1">{item.caption}</p>
            <p className="text-label font-ui text-ink-3">{IMAGE_STATUS_LABELS[item.status]}</p>
            {item.status === "PENDING" ? <HeldReasons reasons={heldReasons(item)} /> : null}
            {item.reviewNote ? <p className="text-label font-ui text-ink-2">{item.reviewNote}</p> : null}
            {canWithdraw(item) ? (
              <ActionGroup align="start">
                <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => onWithdraw(item)}>
                  Take it back
                </Button>
              </ActionGroup>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
