import type { ComponentViews } from "@/lib/componentViewContract";

import { ChartView } from "./ChartView";
import { DrawingView } from "./DrawingView";
import { MapLayerView } from "./MapLayerView";
import { TableView } from "./TableView";
import { TimelineView } from "./TimelineView";

export const VIEWS: ComponentViews = {
  general_drawing: DrawingView,
  general_chart: ChartView,
  general_table: TableView,
  general_timeline: TimelineView,
  general_map_layer: MapLayerView
};
