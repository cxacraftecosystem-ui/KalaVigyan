"use client";

import { useState, type CSSProperties, type ReactNode } from "react";

import { Lightbox } from "@/components/ui/Lightbox";
import { focalPosition, focalViewBox, isCommonsFile, type FocalBox, type PictureRole } from "@/lib/commonsPicture";
import { isLocalRaster, LOCAL_PICTURE_SIZES, localSrcSet } from "@/lib/localPicture";
import { pictureSources, type PictureSources } from "@/lib/pictureSources";
import { cn } from "@/lib/utils";

export type PlateProps = {
  src: string;
  alt: string;
  caption: ReactNode;
  credit: ReactNode;
  role?: PictureRole;
  ratio?: string;
  focal?: FocalBox;
  originalWidth?: number;
  priority?: boolean;
  lightbox?: boolean;
  className?: string;
  pictureClassName?: string;
};

export function focalStyle(focal: FocalBox | undefined): CSSProperties | undefined {
  if (!focal) return undefined;
  return { objectPosition: focalPosition(focal), objectViewBox: focalViewBox(focal) } as CSSProperties;
}

function withLocalSizes(sources: PictureSources): PictureSources {
  if (sources.srcSet || !isLocalRaster(sources.src)) return sources;
  return { ...sources, srcSet: localSrcSet(sources.src), sizes: sources.sizes ?? LOCAL_PICTURE_SIZES };
}

export function PlatePicture({ alt, sources, size, focal, priority, ratio, className, onOpen }: { alt: string; sources: PictureSources; size?: { width: number; height: number }; focal?: FocalBox; priority?: boolean; ratio?: string; className?: string; onOpen?: () => void }) {
  const shown = withLocalSizes(sources);
  const image = (
    <img
      src={shown.src}
      srcSet={shown.srcSet}
      sizes={shown.sizes}
      alt={alt}
      width={size?.width}
      height={size?.height}
      loading={priority ? "eager" : "lazy"}
      fetchPriority={priority ? "high" : undefined}
      decoding="async"
      referrerPolicy="no-referrer"
      crossOrigin={isCommonsFile(shown.src) ? "anonymous" : undefined}
      style={focalStyle(focal)}
    />
  );
  return (
    <div className={cn("kv-photo", className)} style={ratio ? { aspectRatio: ratio } : undefined}>
      {onOpen ? (
        <button type="button" className="kv-photo-button" onClick={onOpen} aria-haspopup="dialog">
          {image}
          <span className="sr-only">Open the picture larger</span>
        </button>
      ) : (
        image
      )}
    </div>
  );
}

export function Plate({ src, alt, caption, credit, role = "plate", ratio = "3 / 2", focal, originalWidth, priority = false, lightbox = true, className, pictureClassName }: PlateProps) {
  const [open, setOpen] = useState(false);
  const sources = pictureSources(src, role, originalWidth);
  return (
    <figure className={cn("min-w-0", className)} data-testid="plate">
      <PlatePicture alt={alt} sources={sources} focal={focal} priority={priority} ratio={ratio} className={pictureClassName} onOpen={lightbox ? () => setOpen(true) : undefined} />
      <figcaption className="mt-3">
        <p className="kv-caption">{caption}</p>
        <p className="kv-credit">{credit}</p>
      </figcaption>
      {lightbox ? <Lightbox picture={{ src: sources.largest, alt, caption, credit }} open={open} onClose={() => setOpen(false)} /> : null}
    </figure>
  );
}
