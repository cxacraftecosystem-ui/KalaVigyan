export type Rgb = readonly [number, number, number];
export type TonePair = { mark: string; paint: string; ground: string };

export const GRAPHIC_CONTRAST = 3;

export const PLACE_TONE_PAIRS: readonly TonePair[] = [
  { mark: "the river course", paint: "--map-river", ground: "--map-land" },
  { mark: "the river course over its halo", paint: "--map-river", ground: "--map-label-halo" },
  { mark: "a reached or waiting district", paint: "--c-terracotta", ground: "--map-land" },
  { mark: "the chosen stretch", paint: "--map-selection", ground: "--map-selection-halo" },
  { mark: "the source's ring", paint: "--map-marker-ring", ground: "--map-land" },
  { mark: "a month's rainfall", paint: "--series-rain", ground: "--c-ground" },
  { mark: "the chosen month's rainfall", paint: "--series-rain", ground: "--c-sunk" },
  { mark: "the wettest month", paint: "--chart-emph", ground: "--c-sunk" }
];

const HEX = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i;
const CHANNELS = /^(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})$/;
const RGB_CALL = /^rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})(?:[\s,/]+[\d.]+%?)?\s*\)$/;

function inRange(channels: number[]): Rgb | null {
  return channels.every((value) => value >= 0 && value <= 255) ? [channels[0], channels[1], channels[2]] : null;
}

export function rgbOf(colour: string): Rgb | null {
  const value = colour.trim();
  const hex = HEX.exec(value);
  if (hex) return inRange(hex.slice(1).map((part) => parseInt(part, 16)));
  const found = CHANNELS.exec(value) ?? RGB_CALL.exec(value);
  return found ? inRange(found.slice(1, 4).map(Number)) : null;
}

function linear(channel: number): number {
  const share = channel / 255;
  return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4;
}

export function luminance([red, green, blue]: Rgb): number {
  return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
}

export function contrastRatio(a: Rgb, b: Rgb): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

export function pairRatio(tokens: ReadonlyMap<string, string>, pair: TonePair): number | null {
  const paint = rgbOf(tokens.get(pair.paint) ?? "");
  const ground = rgbOf(tokens.get(pair.ground) ?? "");
  return paint && ground ? contrastRatio(paint, ground) : null;
}

export function toneProblems(tokens: ReadonlyMap<string, string>, theme: string): string[] {
  return PLACE_TONE_PAIRS.flatMap((pair) => {
    const ratio = pairRatio(tokens, pair);
    if (ratio === null) return [`${theme}: ${pair.paint} or ${pair.ground} is not a colour, so ${pair.mark} cannot be read`];
    return ratio < GRAPHIC_CONTRAST ? [`${theme}: ${pair.mark} (${pair.paint} on ${pair.ground}) is ${ratio.toFixed(2)}:1, under ${GRAPHIC_CONTRAST}:1`] : [];
  });
}
