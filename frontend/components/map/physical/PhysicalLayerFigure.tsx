"use client";

import { useCallback, useMemo, type ReactNode } from "react";

import { DataTable, type DataRow } from "@/components/charts/DataTable";
import { failureMessage, useRemote } from "@/components/hooks/useRemote";
import { MapCanvas, type MapScene } from "@/components/map/MapCanvas";
import { MapRetry } from "@/components/map/MapRetry";
import { MapSourceLine } from "@/components/map/MapSourceLine";
import { MarkControls } from "@/components/map/MarkControls";
import { MineralSymbols } from "@/components/map/physical/MineralsLayer";
import { MineralsSide, ReliefSide, RiversSide } from "@/components/map/physical/PhysicalSide";
import { ReliefOver, ReliefUnder } from "@/components/map/physical/ReliefLayer";
import { RiversOver, RiversUnder } from "@/components/map/physical/RiversLayer";
import { PlaceMarkers, placeMapMarks } from "@/components/map/PlaceMarkers";
import { useMarkFocus } from "@/components/map/useStateRanking";
import { Figure } from "@/components/ui/Figure";
import { Skeleton } from "@/components/ui/Skeleton";
import type { PlaceMarker } from "@/lib/mapFamilies";
import { loadPhysical, mineralFinding, mineralSites, physicalLayer, type MineralsFile, type PhysicalFiles, type PhysicalLayerId, type ReliefFile, type RiversFile } from "@/lib/mapPhysical";

const PLACE_MARKS_LABEL = "Craft places on the map";
const LAYOUT = "grid gap-8 lg:grid-cols-[minmax(0,6.6fr)_minmax(0,4.4fr)] lg:items-start lg:gap-12";

type Drawn = { under: ReactNode; over: (scene: MapScene) => ReactNode; side: ReactNode; dek: string; table: { rows: DataRow[]; node: ReactNode } };

export const PHYSICAL_DEKS: Record<"relief" | "rivers", string> = {
  relief: "Elevation in bands at 100, 300, 600, 1,000, 2,000 and 4,000 m over shaded relief, with the main ranges and the highest named summits.",
  rivers: "Rivers and lake centrelines drawn heavier for the larger rivers, with lakes, reservoirs and the major rivers named."
};

function reliefDrawn(file: ReliefFile): Drawn {
  const rows = file.peaks.map((peak) => ({ key: peak.name, cells: { summit: peak.name, metres: peak.elevation.toLocaleString("en-IN") } }));
  const node = <DataTable caption="Named summits inside the outline" columns={[{ key: "summit", label: "Summit" }, { key: "metres", label: "Metres", numeric: true }]} rows={rows} />;
  return { under: <ReliefUnder file={file} />, over: (scene) => <ReliefOver file={file} scale={scene.scale} />, side: <ReliefSide file={file} />, dek: PHYSICAL_DEKS.relief, table: { rows, node } };
}

function riversDrawn(file: RiversFile): Drawn {
  const rows = [...file.labels].sort((a, b) => a.text.localeCompare(b.text, "en")).map((label) => ({ key: label.text, cells: { river: label.text } }));
  const node = <DataTable caption="Rivers named on the map" columns={[{ key: "river", label: "River" }]} rows={rows} />;
  return { under: <RiversUnder file={file} />, over: () => <RiversOver file={file} />, side: <RiversSide file={file} />, dek: PHYSICAL_DEKS.rivers, table: { rows, node } };
}

const MINERAL_COLUMNS = [
  { key: "site", label: "Site" },
  { key: "state", label: "State" },
  { key: "commodities", label: "Commodities" },
  { key: "status", label: "Status" }
];

function mineralsDrawn(file: MineralsFile): Drawn {
  const sites = mineralSites(file);
  const rows = sites.map((site) => ({ key: String(site.depId), cells: { site: site.name || `MRDS ${site.depId}`, state: site.state, commodities: site.commodities, status: site.status } }));
  const node = <DataTable caption="Mineral deposits" columns={MINERAL_COLUMNS} rows={rows} />;
  return { under: null, over: (scene) => <MineralSymbols sites={sites} scale={scene.scale} />, side: <MineralsSide file={file} sites={sites} />, dek: mineralFinding(sites, file.classes) ?? "", table: { rows, node } };
}

function drawn(id: PhysicalLayerId, file: PhysicalFiles[PhysicalLayerId]): Drawn {
  if (id === "relief") return reliefDrawn(file as ReliefFile);
  if (id === "rivers") return riversDrawn(file as RiversFile);
  return mineralsDrawn(file as MineralsFile);
}

function PhysicalMap({ id, view, markers }: { id: PhysicalLayerId; view: Drawn; markers: readonly PlaceMarker[] }) {
  const focus = useMarkFocus();
  const title = physicalLayer(id).title;
  return (
    <MapCanvas
      title={title}
      description={markers.length ? `${view.dek} Craft places are marked as discs.` : view.dek}
      under={view.under}
      over={(scene) => (
        <>
          {view.over(scene)}
          <PlaceMarkers markers={markers} scene={scene} active={focus.active} />
        </>
      )}
      controls={(scene) => (markers.length ? <MarkControls marks={placeMapMarks(markers, scene.scale)} scene={scene} focus={focus} label={PLACE_MARKS_LABEL} /> : null)}
    />
  );
}

export function PhysicalLayerFigure({ id, markers, caption, controls }: { id: PhysicalLayerId; markers: readonly PlaceMarker[]; caption: string | null; controls?: ReactNode }) {
  const load = useCallback(() => loadPhysical(id), [id]);
  const file = useRemote(load);
  const view = useMemo(() => (file.data ? drawn(id, file.data) : null), [id, file.data]);
  return (
    <Figure number={1} kind="map" id="map-figure" title={physicalLayer(id).title} dek={view?.dek} source={<MapSourceLine caption={caption} counts={false} />} table={view?.table.node} valueCount={view?.table.rows.length}>
      <div className={LAYOUT} data-testid="physical-layer" data-layer={id}>
        <div className="min-w-0">{view ? <PhysicalMap id={id} view={view} markers={markers} /> : <Skeleton shape="chart" label="Drawing the layer" />}</div>
        <div className="grid content-start gap-[18px]">
          {controls}
          {file.failure ? <MapRetry message={failureMessage(file.failure, "This layer could not be drawn. Try again in a moment.")} onRetry={file.retry} /> : view?.side}
        </div>
      </div>
    </Figure>
  );
}
