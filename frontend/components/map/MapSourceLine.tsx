import { NATURAL_EARTH_CREDIT } from "@/components/map/basemap";

export const OSM_CREDIT = "© OpenStreetMap contributors";
export const OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright";
export const BOUNDARY_ATTRIBUTION = "Boundary data: DataMeet.";
export const CRAFT_LIST_COUNTS = "Counts from the KalaVigyan craft list.";

export function MapSourceLine({ caption, counts }: { caption: string | null; counts: boolean }) {
  return (
    <span data-testid="map-attribution">
      {caption ? `${caption} ` : null}
      {NATURAL_EARTH_CREDIT} {BOUNDARY_ATTRIBUTION}
      {counts ? ` ${CRAFT_LIST_COUNTS}` : null}{" "}
      <a href={OSM_COPYRIGHT_URL} target="_blank" rel="noopener noreferrer" className="underline-offset-3 hover:text-indigo-hover hover:underline">
        {OSM_CREDIT}
      </a>
    </span>
  );
}
