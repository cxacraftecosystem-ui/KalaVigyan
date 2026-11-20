export type PhysicalLayerId = "relief" | "rivers" | "minerals";
export type PhysicalLayer = { id: PhysicalLayerId; title: string; hint: string; asset: string };

export const PHYSICAL_GROUP = "Land and water";

export const PHYSICAL_LAYERS: readonly PhysicalLayer[] = [
  { id: "relief", title: "Physical relief and mountains", hint: "ETOPO1 elevation", asset: "/layers/relief.json" },
  { id: "rivers", title: "Rivers and lakes", hint: "Natural Earth 1:10m", asset: "/layers/rivers.json" },
  { id: "minerals", title: "Mineral deposits", hint: "USGS Mineral Resources Data System", asset: "/layers/minerals.json" }
];

export type DatasetRow = { dataset: string; url: string; sha256: string; version?: string; publisher?: string; licence?: string; citation?: string };
export type PlacedLabel = { text: string; tier: number; longitude: number; latitude: number; angle: number };
export type Peak = { name: string; elevation: number; text: string; rank: number; longitude: number; latitude: number };

export type RiversFile = { source: string; site: string; licence: string; datasets: DatasetRow[]; ranks: { rank: number; lines: string }[]; lakes: string[]; labels: PlacedLabel[] };
export type ShadeImage = { href: string; west: number; south: number; east: number; north: number };
export type ReliefFile = { source: string; licence: string; datasets: DatasetRow[]; breaks: number[]; bands: { min: number; rings: string[] }[]; shade: ShadeImage; ranges: PlacedLabel[]; peaks: Peak[] };
export type MineralRow = [number, string, string, number, number, number, number, string];
export type MineralsFile = { source: DatasetRow; classes: { id: string; label: string }[]; statuses: string[]; sites: MineralRow[] };
export type PhysicalFiles = { relief: ReliefFile; rivers: RiversFile; minerals: MineralsFile };

export type MineralSite = { depId: number; name: string; state: string; longitude: number; latitude: number; classIndex: number; status: string; commodities: string };

export function physicalLayerId(requested: string | null): PhysicalLayerId | null {
  return PHYSICAL_LAYERS.find((layer) => layer.id === requested)?.id ?? null;
}

export function physicalLayer(id: PhysicalLayerId): PhysicalLayer {
  return PHYSICAL_LAYERS.find((layer) => layer.id === id) as PhysicalLayer;
}

export function physicalOptions(): { value: string; label: string; group: string; hint: string }[] {
  return PHYSICAL_LAYERS.map((layer) => ({ value: layer.id, label: layer.title, group: PHYSICAL_GROUP, hint: layer.hint }));
}

export function sentenceCase(text: string): string {
  return text ? `${text.charAt(0).toUpperCase()}${text.slice(1).toLowerCase()}` : text;
}

export function mineralSites(file: MineralsFile): MineralSite[] {
  return file.sites.map(([depId, name, state, longitude, latitude, classIndex, statusIndex, commodities]) => ({
    depId,
    name,
    state,
    longitude,
    latitude,
    classIndex,
    status: sentenceCase(file.statuses[statusIndex] ?? "Unknown"),
    commodities
  }));
}

export type Tally = { key: string; label: string; count: number };

export function tally(keys: readonly string[], labels: (key: string) => string = (key) => key): Tally[] {
  const counts = new Map<string, number>();
  for (const key of keys) if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
  return [...counts.entries()].map(([key, count]) => ({ key, label: labels(key), count })).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "en"));
}

export function mineralFinding(sites: readonly MineralSite[], classes: readonly { label: string }[]): string | null {
  const states = tally(sites.map((site) => site.state));
  const leading = tally(sites.map((site) => String(site.classIndex)));
  if (!states.length || !leading.length) return null;
  const top = classes[Number(leading[0].key)]?.label.toLowerCase() ?? "";
  return `${states[0].label} holds ${states[0].count} of the ${sites.length.toLocaleString("en-IN")} recorded deposits; the largest class, with ${leading[0].count}, is ${top}.`;
}

export function riverWidth(rank: number): number {
  if (rank <= 3) return 1.9;
  if (rank <= 6) return 1.35;
  if (rank <= 8) return 0.95;
  return 0.7;
}

export function elevationBands(file: ReliefFile): { min: number | null; max: number | null }[] {
  const edges: (number | null)[] = [null, ...file.breaks, null];
  return edges.slice(0, -1).map((min, at) => ({ min, max: edges[at + 1] }));
}

const cache = new Map<string, Promise<unknown>>();

export function loadPhysical<K extends PhysicalLayerId>(id: K): Promise<PhysicalFiles[K]> {
  const asset = physicalLayer(id).asset;
  const pending =
    cache.get(asset) ??
    fetch(asset, { cache: "force-cache" }).then((response) => {
      if (!response.ok) throw new Error(`${asset} returned ${response.status}`);
      return response.json();
    });
  cache.set(asset, pending);
  pending.catch(() => cache.delete(asset));
  return pending as Promise<PhysicalFiles[K]>;
}
