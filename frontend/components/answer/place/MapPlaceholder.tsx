import { Skeleton } from "@/components/ui/Skeleton";

export function MapPlaceholder() {
  return (
    <div className="min-w-0" data-testid="map-placeholder">
      <Skeleton shape="chart" label="Drawing the map" />
    </div>
  );
}
