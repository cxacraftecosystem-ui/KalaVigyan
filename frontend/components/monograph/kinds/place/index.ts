import type { ComponentViews } from "@/lib/componentViewContract";
import { WHY_HERE_KIND } from "@/lib/placeGround";

import { WhyHereView } from "./WhyHereView";

export const VIEWS: ComponentViews = {
  [WHY_HERE_KIND]: WhyHereView
};
