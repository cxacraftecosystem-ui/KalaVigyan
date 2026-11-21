import { PLACE_ROLE_LABEL } from "@/lib/craftPlaces";
import { formatMeasure, formatNumber } from "@/lib/measure";
import type { Elevation, GroundAt, GroundLayer, GroundLayerKey, GroundNote, GroundPlace, GroundReading, MaterialDeposits, NoteReading, Water } from "@/lib/placeGround";
import type { RegionDataset } from "@/lib/regionContract";
import { periodText, valueLabel } from "@/lib/regionView";

export const ELEVATION_BREAKS = [100, 300, 600, 1000, 2000, 4000] as const;
export const PLACES_NAMED = 3;

export const READING_TITLE: Readonly<Record<NoteReading, string>> = {
  elevation: "Elevation",
  river: "Nearest river",
  lake: "Nearest lake",
  deposits: "Deposits",
  rainfall: "Rainfall",
  soil: "Soil",
  cover: "Cover"
};

export const LAYER_SHORT: Readonly<Record<GroundLayerKey, string>> = {
  ETOPO1: "ETOPO1",
  NE_RIVERS: "Natural Earth 1:10m rivers",
  NE_LAKES: "Natural Earth 1:10m lakes",
  USGS_MRDS: "USGS MRDS"
};

const COMMODITY_WORDS: Readonly<Record<string, string>> = {
  Aluminum: "aluminium",
  "Stone, Dimension": "dimension stone",
  "Gypsum-Anhydrite": "gypsum",
  "Boron-Borates": "borate",
  "Barium-Barite": "barite",
  "Phosphorus-Phosphates": "phosphate",
  "Fluorine-Fluorite": "fluorite",
  "Sulfur-Pyrite": "pyrite",
  Sulfur: "sulphur",
  "Sodium Sulfate": "sodium sulphate",
  Halite: "rock salt",
  REE: "rare earth"
};

export function metres(value: number): string {
  return `${formatNumber(value, 0)} m`;
}

export function elevationText(elevation: Elevation): string {
  if (elevation.lowM === null) return `Below ${metres(elevation.highM ?? ELEVATION_BREAKS[0])}`;
  if (elevation.highM === null) return `Above ${metres(elevation.lowM)}`;
  return `${formatNumber(elevation.lowM, 0)}–${metres(elevation.highM)}`;
}

export function elevationStep(lowM: number | null): number {
  if (lowM === null) return 1;
  const at = (ELEVATION_BREAKS as readonly number[]).indexOf(lowM);
  return at < 0 ? 1 : at + 2;
}

export function bandText(lowM: number | null): string {
  const step = elevationStep(lowM);
  const high = step <= ELEVATION_BREAKS.length ? ELEVATION_BREAKS[step - 1] : null;
  return elevationText({ lowM, highM: high });
}

export function km(value: number): string {
  return `${formatNumber(value)} km`;
}

export function waterText(water: Water | null): string | null {
  return water ? km(water.distanceKm) : null;
}

export function commodityWord(name: string): string {
  return COMMODITY_WORDS[name] ?? name.toLowerCase();
}

export function listText(words: readonly string[], joiner = "and"): string {
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} ${joiner} ${words[words.length - 1]}`;
}

export function depositTotal(at: GroundAt): number {
  return at.depositClasses.reduce((sum, tally) => sum + tally.count, 0);
}

export function depositsText(at: GroundAt, radiusKm: number): string {
  const total = depositTotal(at);
  return `${formatNumber(total, 0)} within ${radiusKm} km`;
}

export function materialSentence(match: MaterialDeposits, radiusKm: number, place: string): string {
  const noun = match.count === 1 ? "deposit" : "deposits";
  const commodities = listText(match.commodities.map(commodityWord), "or");
  return `${formatNumber(match.count, 0)} recorded ${commodities} ${noun} within ${radiusKm} km of ${place}, the nearest ${km(match.nearestKm)} away.`;
}

export function readingLabel(reading: GroundReading): string {
  return valueLabel({ variable: reading.variable, depth: reading.depth, period: reading.period });
}

export function readingValue(reading: GroundReading): string {
  return formatMeasure(reading.value, reading.unit);
}

export function layerNote(layer: GroundLayer | undefined): string {
  return layer ? `${LAYER_SHORT[layer.key]}, ${layer.edition}` : "";
}

export function datasetNote(dataset: RegionDataset | undefined, reading: GroundReading): string {
  return [dataset?.title, dataset?.edition, reading.resolution, periodText(reading.period)].filter(Boolean).join(" · ");
}

export function placeLine(place: GroundPlace): string {
  const roles = place.roles.map((role) => PLACE_ROLE_LABEL[role]).join(" · ");
  const where = [place.district, place.state].filter(Boolean).join(", ");
  return [roles, where].filter(Boolean).join(" · ");
}

export function placesTitle(places: readonly Pick<GroundPlace, "name">[]): string {
  const names = places.map((place) => place.name);
  if (names.length <= PLACES_NAMED) return listText(names);
  const rest = names.length - (PLACES_NAMED - 1);
  return `${names.slice(0, PLACES_NAMED - 1).join(", ")} and ${rest} more places`;
}

export function frameDek(radiusKm: number, places: number): string {
  const around = places === 1 ? "the place" : `each of the ${places} places`;
  return `Relief in elevation bands, rivers and lakes, and every mineral deposit on record within ${radiusKm} km of ${around} where the craft is practised.`;
}

export function notesFor(notes: readonly GroundNote[], reading: NoteReading): string[] {
  return notes.filter((note) => note.reading === reading).map((note) => note.unit);
}

export function layerOf(layers: readonly GroundLayer[], key: GroundLayerKey): GroundLayer | undefined {
  return layers.find((layer) => layer.key === key);
}
