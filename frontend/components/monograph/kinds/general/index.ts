import type { ComponentViews } from "@/lib/componentViewContract";

import { ChartView } from "./ChartView";
import { DrawingView } from "./DrawingView";
import { MapLayerView } from "./MapLayerView";
import { TableView } from "./TableView";
import { TimelineView } from "./TimelineView";

export const VIEWS: ComponentViews = {
  drawing: DrawingView
};

export const DECLARED_VIEWS: ComponentViews = {
  chart: ChartView,
  fact_table: TableView,
  timeline: TimelineView,
  map_layer: MapLayerView
};
