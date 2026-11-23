import { COMMONS_WIDTHS, commonsSrcSet, commonsThumb, isCommonsFile, PICTURE_SIZES, PICTURE_WIDTHS, type PictureRole } from "@/lib/commonsPicture";
import { isLocalRaster, localSrcSet } from "@/lib/localPicture";

export type PictureSources = { src: string; srcSet?: string; sizes?: string; largest: string };

export function pictureSources(src: string, role: PictureRole, originalWidth?: number): PictureSources {
  if (isLocalRaster(src)) return { src, srcSet: localSrcSet(src, originalWidth), sizes: PICTURE_SIZES[role], largest: src };
  if (!isCommonsFile(src)) return { src, largest: src };
  const widths = PICTURE_WIDTHS[role];
  const largest = [...COMMONS_WIDTHS].reverse().find((width) => !originalWidth || width < originalWidth) ?? COMMONS_WIDTHS[0];
  return {
    src: commonsThumb(src, widths[Math.min(1, widths.length - 1)]),
    srcSet: commonsSrcSet(src, widths, originalWidth),
    sizes: PICTURE_SIZES[role],
    largest: commonsThumb(src, largest)
  };
}
