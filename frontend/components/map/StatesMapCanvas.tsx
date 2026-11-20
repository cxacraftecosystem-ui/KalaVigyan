"use client";

import { MapCanvas } from "@/components/map/MapCanvas";
import { MarkControls } from "@/components/map/MarkControls";
import { StateCircles } from "@/components/map/StateCircles";
import { useMarkFocus, type StateRanking } from "@/components/map/useStateRanking";
import { mapDescription } from "@/lib/mapStates";

export const STATE_MARKS_LABEL = "States on the map";

export function StatesMapCanvas({ ranking, title }: { ranking: StateRanking; title: string }) {
  const focus = useMarkFocus();
  const emph = ranking.circles[0]?.name ?? null;
  return (
    <MapCanvas
      title={title}
      description={mapDescription(ranking.circles)}
      over={(scene) => <StateCircles circles={ranking.circles} emphKey={emph} scene={scene} active={focus.active} />}
      controls={(scene) => (ranking.marks.length ? <MarkControls marks={ranking.marks} scene={scene} focus={focus} label={STATE_MARKS_LABEL} /> : null)}
    />
  );
}
