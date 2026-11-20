"use client";

import { useEffect, useMemo } from "react";

import { previewable, shownCredit, type ImageOrigin } from "@/lib/imageContributionContract";

type Preview = { file: File | null; origin: ImageOrigin; generator: string; caption: string; altText: string };

export function PicturePreview({ file, origin, generator, caption, altText }: Preview) {
  const url = useObjectUrl(file && previewable(file) ? file : null);
  if (!file) return null;
  return (
    <figure className="grid gap-2 border-t border-ink-1 pt-4" data-testid="picture-preview">
      <p className="kicker">As it will be shown</p>
      {url ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- a local object URL of the chosen file, nothing for next/image to optimise */}
          <img src={url} alt={altText.trim() || file.name} className="aspect-[4/3] w-full rounded-plate bg-sunk object-contain" />
        </>
      ) : (
        <p className="grid aspect-[4/3] w-full place-items-center rounded-plate bg-sunk p-6 text-center text-label font-ui text-ink-2">
          {file.name} is made a WebP picture when it arrives; it is shown in your pictures once it is sent.
        </p>
      )}
      <figcaption className="grid gap-1">
        {caption.trim() ? <span className="text-figcaption font-reading italic text-ink-2">{caption.trim()}</span> : null}
        <span className="text-caption font-ui text-ink-3">{shownCredit(origin, generator)}</span>
      </figcaption>
    </figure>
  );
}

function useObjectUrl(file: File | null): string | null {
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);
  return url;
}
