import { NATURAL_EARTH_CREDIT } from "@/components/map/basemap";
import { BOUNDARY_ATTRIBUTION, DISTRICTS_INDICATIVE, OSM_COPYRIGHT_URL, OSM_CREDIT, SURVEY_OF_INDIA_CAPTION } from "@/components/map/MapAttribution";
import type { BoundaryNote } from "@/lib/regionContract";

export function boundaryCaption(boundary: BoundaryNote | null, districts: boolean): string {
  if (boundary) return boundary.caption;
  return districts ? `${SURVEY_OF_INDIA_CAPTION} ${DISTRICTS_INDICATIVE}` : SURVEY_OF_INDIA_CAPTION;
}

export function MapSourceLine({ boundary, districts, counts }: { boundary: BoundaryNote | null; districts: boolean; counts: boolean }) {
  return (
    <span data-testid="map-attribution">
      {boundaryCaption(boundary, districts)} {NATURAL_EARTH_CREDIT} {BOUNDARY_ATTRIBUTION}
      {counts ? " Counts from the KalaVigyan craft list." : null}{" "}
      <a href={OSM_COPYRIGHT_URL} target="_blank" rel="noopener noreferrer" className="underline-offset-3 hover:text-indigo-hover hover:underline">
        {OSM_CREDIT}
      </a>
    </span>
  );
}
