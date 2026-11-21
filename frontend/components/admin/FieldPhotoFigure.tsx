"use client";

import { useState } from "react";

import { Lightbox } from "@/components/ui/Lightbox";
import { TextLink } from "@/components/ui/TextLink";
import type { FieldPhoto } from "@/lib/fieldPhotoReviewContract";
import { keptRegion, sizeLine, trimsOfCrop, type Trims } from "@/lib/fieldPhotoReviewView";

type Opened = "original" | "crop" | null;

export function FieldPhotoFigure({ photo, trims }: { photo: FieldPhoto; trims: Trims | null }) {
  const [opened, setOpened] = useState<Opened>(null);
  const decidedCrop = photo.decision?.current && photo.decision.crop ? trimsOfCrop(photo.decision.crop, photo.width, photo.height) : null;
  const shade = trims ?? decidedCrop;
  const credit = `${photo.credit} · ${photo.publisher}`;
  const caption = photo.caption ?? photo.alt;
  const cropUrl = photo.decision?.current ? photo.decision.cropUrl : null;

  return (
    <figure className="grid min-w-0 content-start gap-3" data-testid="field-photo-figure">
      <div className="relative mx-auto w-full overflow-hidden rounded-plate bg-sunk" style={{ aspectRatio: `${photo.width} / ${photo.height}`, maxWidth: `calc(75vh * ${(photo.width / photo.height).toFixed(4)})` }}>
        {photo.fileUrl ? (
          <button type="button" className="block size-full cursor-zoom-in" onClick={() => setOpened("original")} aria-haspopup="dialog">
            <>
              {/* eslint-disable-next-line @next/next/no-img-element -- a presigned bucket link to a private copy, nothing for next/image to optimise */}
              <img src={photo.fileUrl} alt={photo.alt} width={photo.width} height={photo.height} className="size-full object-contain" loading="lazy" referrerPolicy="no-referrer" />
            </>
            <span className="sr-only">Open the photograph larger</span>
          </button>
        ) : (
          <p className="grid size-full place-items-center p-6 text-center font-ui text-label text-ink-2">The stored copy cannot be opened right now.</p>
        )}
        {shade ? <CropShade trims={shade} /> : null}
      </div>
      <figcaption className="grid gap-1">
        <p className="kv-caption">{caption}</p>
        <p className="kv-credit">{credit}</p>
        <p className="font-ui text-caption text-ink-3 tabular-nums lining-nums">{sizeLine(photo)}</p>
        {cropUrl ? (
          <TextLink standalone className="justify-self-start" onClick={() => setOpened("crop")}>
            Open the crop as pages show it
          </TextLink>
        ) : null}
      </figcaption>
      {photo.fileUrl ? (
        <Lightbox
          picture={{ src: photo.fileUrl, alt: photo.alt, width: photo.width, height: photo.height, caption, credit }}
          open={opened === "original"}
          onClose={() => setOpened(null)}
        />
      ) : null}
      {cropUrl ? <Lightbox picture={{ src: cropUrl, alt: photo.alt, caption, credit }} open={opened === "crop"} onClose={() => setOpened(null)} /> : null}
    </figure>
  );
}

function CropShade({ trims }: { trims: Trims }) {
  const kept = keptRegion(trims);
  const hole = `M${kept.x} ${kept.y}V${kept.y + kept.height}H${kept.x + kept.width}V${kept.y}Z`;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden className="pointer-events-none absolute inset-0 size-full" data-testid="field-photo-crop">
      <path d={`M0 0H100V100H0Z ${hole}`} fillRule="evenodd" fillOpacity={0.62} className="fill-current text-ink-1" />
      <rect x={kept.x} y={kept.y} width={kept.width} height={kept.height} vectorEffect="non-scaling-stroke" strokeWidth={2} className="fill-none stroke-current text-ground" />
    </svg>
  );
}
