"use client";

import { useState } from "react";

import { pictureSources } from "@/components/editorial/Plate";
import { Lightbox } from "@/components/ui/Lightbox";
import { mediaCredit } from "@/lib/answerEssay";
import type { PictureRole } from "@/lib/commonsPicture";
import type { MediaRef } from "@/lib/explainerBlockBase";
import { cn } from "@/lib/utils";

function Credit({ media }: { media: MediaRef }) {
  return (
    <>
      {mediaCredit(media)}
      {" · "}
      <a href={media.pageUrl} target="_blank" rel="noopener noreferrer" className="kv-link font-normal">
        {media.title}
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
    </>
  );
}

export function MediaPlate({ media, role = "plate", className }: { media: MediaRef; role?: PictureRole; className?: string }) {
  const [broken, setBroken] = useState(false);
  const [open, setOpen] = useState(false);
  if (broken) return null;
  const sources = pictureSources(media.imageUrl, role, media.width ?? undefined);
  const ratio = media.width && media.height ? `${media.width} / ${media.height}` : "4 / 3";
  return (
    <figure className={cn("min-w-0", className)} data-display={media.display} data-testid="media-plate">
      <div className="kv-photo max-h-[70vh]" style={{ aspectRatio: ratio }}>
        <button type="button" className="kv-photo-button" onClick={() => setOpen(true)} aria-haspopup="dialog">
          {/* eslint-disable-next-line @next/next/no-img-element -- Commons pictures load at their standard widths through commonsThumb, which next/image would not request */}
          <img src={sources.src} srcSet={sources.srcSet} sizes={sources.sizes} alt={media.alt} loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
          <span className="sr-only">Open the picture larger</span>
        </button>
      </div>
      <figcaption className="mt-3">
        <p className="kv-caption">{media.alt}</p>
        <p className="kv-credit">
          <Credit media={media} />
        </p>
      </figcaption>
      <Lightbox picture={{ src: sources.largest, alt: media.alt, caption: media.alt, credit: <Credit media={media} /> }} open={open} onClose={() => setOpen(false)} />
    </figure>
  );
}
