"use client";

import { MediaCredit, MediaPlate } from "@/components/answer/MediaPlate";
import { pictureSources } from "@/lib/pictureSources";
import type { MediaRef } from "@/lib/explainerBlockBase";
import type { ImagesBlock } from "@/lib/explainerContract";

export function PictureView({ media, onBroken }: { media: MediaRef; onBroken: () => void }) {
  const sources = pictureSources(media.imageUrl, "plate", media.width ?? undefined);
  return (
    <figure className="grid min-w-0 gap-2" data-display={media.display}>
      <a href={media.pageUrl} target="_blank" rel="noopener noreferrer" className="kv-photo block aspect-[4/3]">
        {/* eslint-disable-next-line @next/next/no-img-element -- Commons pictures load at their standard widths through commonsThumb, which next/image would not request */}
        <img src={sources.src} srcSet={sources.srcSet} sizes={sources.sizes} alt={media.alt} loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={onBroken} />
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
      <figcaption className="break-words font-ui text-caption text-ink-3">
        <MediaCredit media={media} />
      </figcaption>
    </figure>
  );
}

export function ImageStrip({ block }: { block: ImagesBlock }) {
  return (
    <ul className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3" aria-label="Pictures" data-testid="image-strip">
      {block.items.map((item) => (
        <li key={item.media.id} className="min-w-0">
          <MediaPlate media={item.media} />
        </li>
      ))}
    </ul>
  );
}
