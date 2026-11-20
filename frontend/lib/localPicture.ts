import { COMMONS_WIDTHS } from "@/lib/commonsPicture";

export const LOCAL_PICTURE_QUALITY = 80;
export const LOCAL_PICTURE_SIZES = "100vw";

const OPTIMIZER = "/_next/image";
const RASTER = /\.(?:jpe?g|png|webp|avif)$/i;

export function isLocalRaster(src: string): boolean {
  return src.startsWith("/") && !src.startsWith("//") && RASTER.test(src);
}

export function optimizedPicture(src: string, width: number): string {
  return `${OPTIMIZER}?url=${encodeURIComponent(src)}&w=${width}&q=${LOCAL_PICTURE_QUALITY}`;
}

export function localSrcSet(src: string, originalWidth?: number): string {
  if (!originalWidth) return COMMONS_WIDTHS.map((width) => `${optimizedPicture(src, width)} ${width}w`).join(", ");
  const smaller = COMMONS_WIDTHS.filter((width) => width < originalWidth);
  return [...smaller.map((width) => `${optimizedPicture(src, width)} ${width}w`), `${src} ${originalWidth}w`].join(", ");
}
