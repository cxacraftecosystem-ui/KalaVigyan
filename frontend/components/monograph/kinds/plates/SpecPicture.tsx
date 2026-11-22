import { commonsThumb } from "@/lib/commonsPicture";
import { THEME_VARIANTS } from "@/lib/componentSpecsGeneral";
import type { Picture } from "@/lib/componentSpecsPlates";
import { isLocalRaster, LOCAL_PICTURE_SIZES, localSrcSet } from "@/lib/localPicture";

import "../general/themes.css";

const COMMONS_UPLOAD = "https://upload.wikimedia.org/";
const PLATE_WIDTH = 960;

export function pictureSource(picture: Picture): string {
  return picture.src.startsWith(COMMONS_UPLOAD) ? commonsThumb(picture.src, Math.min(PLATE_WIDTH, picture.width)) : picture.src;
}

export function focalPosition(picture: Picture): string | undefined {
  const focal = picture.focal;
  if (!focal) return undefined;
  const centre = (start: number, size: number) => `${Math.round((start + size / 2) * 1000) / 10}%`;
  return `${centre(focal.x, focal.width)} ${centre(focal.y, focal.height)}`;
}

export function pictureWidths(picture: Picture): { srcSet?: string; sizes?: string } {
  if (!isLocalRaster(picture.src)) return {};
  return { srcSet: localSrcSet(picture.src, picture.width), sizes: LOCAL_PICTURE_SIZES };
}

function ThemedPicture({ picture, className }: { picture: Picture; className?: string }) {
  return THEME_VARIANTS.map((variant) => (
    // eslint-disable-next-line @next/next/no-img-element -- a contributed drawing is served once per theme and the page shows the one its reader's theme asks for
    <img
      key={variant}
      className={[className, "kv-themed"].filter(Boolean).join(" ")}
      data-theme-variant={variant}
      src={`${picture.src}?theme=${variant}`}
      width={picture.width}
      height={picture.height}
      alt={picture.alt}
      loading={picture.loading ?? undefined}
      decoding={picture.decoding ?? undefined}
      style={picture.focal ? { objectPosition: focalPosition(picture) } : undefined}
    />
  ));
}

export function SpecPicture({ picture, className }: { picture: Picture; className?: string }) {
  if (picture.themed) return <ThemedPicture picture={picture} className={className} />;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- the approved page's own picture, offered at the standard widths through the image service
    <img
      className={className}
      src={pictureSource(picture)}
      {...pictureWidths(picture)}
      width={picture.width}
      height={picture.height}
      alt={picture.alt}
      loading={picture.loading ?? undefined}
      fetchPriority={picture.fetchPriority ?? undefined}
      decoding={picture.decoding ?? undefined}
      crossOrigin={picture.src.startsWith(COMMONS_UPLOAD) ? "anonymous" : undefined}
      style={picture.focal ? { objectPosition: focalPosition(picture) } : undefined}
    />
  );
}
