"use client";

import Link from "next/link";
import { useEffect, useId, useRef, type RefObject } from "react";
import { X } from "lucide-react";

import { countLine, type MapMark } from "@/components/map/markPlacement";
import { AnchoredPopover } from "@/components/ui/AnchoredPopover";
import { Sheet } from "@/components/ui/Sheet";
import { TextLink } from "@/components/ui/TextLink";
import { craftHref } from "@/lib/atlasCollection";

export type PanelSurface = "popover" | "sheet";

export const PANEL_WIDTH_PX = 440;
const POPOVER_FROM_PX = 640;

export function panelSurface(viewportWidth: number): PanelSurface {
  return viewportWidth < POPOVER_FROM_PX ? "sheet" : "popover";
}

export function MarkPanelBody({ mark, headingId, onClose, closeRef }: { mark: MapMark; headingId: string; onClose: () => void; closeRef?: RefObject<HTMLButtonElement | null> }) {
  return (
    <div className="grid gap-3" data-testid="map-mark-panel">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="kicker">{mark.kind}</p>
          <h2 id={headingId} className="mt-1 font-reading text-h3 text-ink-1">
            {mark.name}
          </h2>
          <p className="mt-0.5 font-ui text-label text-ink-3 [font-variant-numeric:lining-nums_tabular-nums]">{`${countLine(mark.count)} practised here`}</p>
        </div>
        <button ref={closeRef} type="button" className="kv-close" onClick={onClose} aria-label={`Close ${mark.name}`}>
          <X aria-hidden />
        </button>
      </div>
      <ul className="grid max-h-[min(55vh,26rem)] gap-x-5 overflow-y-auto overscroll-contain border-t border-rule pt-2 sm:grid-cols-2" data-testid="map-mark-crafts">
        {mark.crafts.map((craft) => (
          <li key={craft.slug} className="border-b border-rule py-1.5">
            <Link href={craftHref(craft)} className="kv-link font-ui text-ui">
              {craft.name}
            </Link>
            {craft.monograph ? <span className="ms-1.5 rounded-plate border border-current px-[5px] py-px font-ui text-caption font-medium text-ink-2">Monograph</span> : null}
          </li>
        ))}
      </ul>
      {mark.more ? (
        <p>
          <TextLink href={mark.more.href} standalone>
            {mark.more.label}
          </TextLink>
        </p>
      ) : null}
    </div>
  );
}

export function MarkPanel({ mark, surface, anchorRef, onClose }: { mark: MapMark | null; surface: PanelSurface; anchorRef: RefObject<HTMLButtonElement | null>; onClose: () => void }) {
  const id = useId();
  const headingId = `${id}-heading`;
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const closeAndReturn = () => {
    onClose();
    anchorRef.current?.focus({ preventScroll: true });
  };
  useEffect(() => {
    if (!mark || surface !== "popover") return;
    const frame = requestAnimationFrame(() => closeRef.current?.focus({ preventScroll: true }));
    return () => cancelAnimationFrame(frame);
  }, [mark, surface]);
  const body = mark ? <MarkPanelBody mark={mark} headingId={headingId} onClose={closeAndReturn} closeRef={closeRef} /> : null;
  return (
    <>
      <Sheet open={mark !== null && surface === "sheet"} onClose={onClose} labelledBy={headingId} panelId={`${id}-panel`}>
        {body}
      </Sheet>
      <AnchoredPopover
        open={mark !== null && surface === "popover"}
        onClose={onClose}
        anchorRef={anchorRef}
        label={mark?.name ?? ""}
        labelledBy={headingId}
        panelId={`${id}-panel`}
        maxWidth={PANEL_WIDTH_PX}
        className="w-[min(440px,calc(100vw-32px))] px-[1.125rem] pt-4 pb-3.5"
      >
        {body}
      </AnchoredPopover>
    </>
  );
}
