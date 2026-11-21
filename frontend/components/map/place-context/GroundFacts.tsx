import type { ReactNode } from "react";

import { FactGrid, type Fact } from "@/components/editorial/FactGrid";
import { MineralSymbol } from "@/components/map/physical/MineralsLayer";
import type { GroundAt, GroundLayer, GroundReading, MineralClass, NoteReading } from "@/lib/placeGround";
import { datasetNote, depositsText, depositTotal, elevationText, layerNote, layerOf, readingLabel, readingValue, waterText } from "@/lib/placeGroundView";
import type { RegionDataset } from "@/lib/regionContract";

export type NotesFor = (reading: NoteReading) => ReactNode;
export type GroundFactsProps = {
  at: GroundAt;
  radiusKm: number;
  layers: readonly GroundLayer[];
  datasets: readonly RegionDataset[];
  classes: readonly MineralClass[];
  notes?: NotesFor;
};

const NUMBERS = "[font-variant-numeric:lining-nums_tabular-nums]";

function Reading({ value, note, children }: { value: string; note: string; children?: ReactNode }) {
  return (
    <>
      <span className={`block font-ui text-ui-lg text-ink-1 ${NUMBERS}`}>{value}</span>
      {children}
      <span className="mt-1 block font-ui text-caption text-ink-3">{note}</span>
    </>
  );
}

function ClassTally({ at, classes }: { at: GroundAt; classes: readonly MineralClass[] }) {
  return (
    <span className="mt-1.5 grid gap-1" data-testid="ground-classes">
      {at.depositClasses.map((tally) => {
        const index = classes.findIndex((found) => found.id === tally.key);
        return (
          <span key={tally.key} className="flex items-center gap-2 font-ui text-label text-ink-2">
            <MineralSymbol classIndex={Math.max(0, index)} size={8} />
            <span className="min-w-0 flex-1">{tally.label}</span>
            <b className={`font-medium text-ink-1 ${NUMBERS}`}>{tally.count}</b>
          </span>
        );
      })}
    </span>
  );
}

function withNotes(value: ReactNode, notes: ReactNode): ReactNode {
  return notes ? (
    <>
      {value}
      <span className="mt-2 block font-reading text-body-sm text-ink-1" data-testid="ground-note">
        {notes}
      </span>
    </>
  ) : (
    value
  );
}

function waterFacts({ at, layers, notes }: GroundFactsProps): Fact[] {
  const facts: Fact[] = [];
  const river = waterText(at.river);
  const lake = waterText(at.lake);
  if (river) facts.push({ label: "Nearest river", value: withNotes(<Reading value={river} note={layerNote(layerOf(layers, "NE_RIVERS"))} />, notes?.("river")) });
  if (lake) facts.push({ label: "Nearest lake or reservoir", value: withNotes(<Reading value={lake} note={layerNote(layerOf(layers, "NE_LAKES"))} />, notes?.("lake")) });
  return facts;
}

function depositFacts(props: GroundFactsProps): Fact[] {
  const { at, radiusKm, layers, classes, notes } = props;
  if (depositTotal(at) === 0) return [];
  const value = (
    <Reading value={depositsText(at, radiusKm)} note={layerNote(layerOf(layers, "USGS_MRDS"))}>
      <ClassTally at={at} classes={classes} />
    </Reading>
  );
  return [{ label: "Mineral deposits on record", value: withNotes(value, notes?.("deposits")) }];
}

function readingFacts({ at, datasets, notes }: GroundFactsProps): Fact[] {
  const noted = new Set<string>();
  return at.readings.map((reading: GroundReading) => {
    const dataset = datasets.find((found) => found.code === reading.datasetCode);
    const first = !noted.has(reading.reading);
    noted.add(reading.reading);
    const value = <Reading value={readingValue(reading)} note={datasetNote(dataset, reading)} />;
    return { label: readingLabel(reading), value: withNotes(value, first ? notes?.(reading.reading) : null) };
  });
}

export function groundFacts(props: GroundFactsProps): Fact[] {
  const elevation = { label: "Elevation", value: withNotes(<Reading value={elevationText(props.at.elevation)} note={layerNote(layerOf(props.layers, "ETOPO1"))} />, props.notes?.("elevation")) };
  return [elevation, ...waterFacts(props), ...depositFacts(props), ...readingFacts(props)];
}

export function GroundFacts(props: GroundFactsProps & { className?: string }) {
  return <FactGrid facts={groundFacts(props)} columns={2} className={props.className} />;
}
