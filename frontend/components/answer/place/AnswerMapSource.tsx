import { MapSourceLine } from "@/components/map/MapSourceLine";
import { safeOutboundUrl } from "@/lib/citations";
import type { BoundaryNote } from "@/lib/regionContract";

const LINK = "underline-offset-3 hover:text-indigo-hover hover:underline";

export const COORDINATES_CREDIT = "Coordinates: Wikidata.";

function BoundaryDataset({ boundary }: { boundary: BoundaryNote }) {
  const href = safeOutboundUrl(boundary.dataset.url);
  return (
    <span data-testid="map-boundary-dataset">
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className={LINK}>
          {boundary.dataset.title}
        </a>
      ) : (
        boundary.dataset.title
      )}
      {boundary.dataset.publisher ? `, ${boundary.dataset.publisher}` : null}.
    </span>
  );
}

export function AnswerMapSource({ boundary, caption = boundary?.caption ?? null, coordinates = false }: { boundary: BoundaryNote | null; caption?: string | null; coordinates?: boolean }) {
  return (
    <>
      <MapSourceLine caption={caption} counts={false} />
      {boundary ? (
        <>
          {" "}
          <BoundaryDataset boundary={boundary} />
        </>
      ) : null}
      {coordinates ? ` ${COORDINATES_CREDIT}` : null}
    </>
  );
}
