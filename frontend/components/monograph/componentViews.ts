import { withDeclared } from "@/components/monograph/eitherView";
import { VIEWS as BLOCK_VIEWS } from "@/components/monograph/kinds/blocks";
import { VIEWS as DATA_VIEWS } from "@/components/monograph/kinds/data";
import { KinCraftsView } from "@/components/monograph/kinds/data/KinCraftsView";
import { DECLARED_VIEWS, VIEWS as GENERAL_VIEWS } from "@/components/monograph/kinds/general";
import { VIEWS as PLACE_VIEWS } from "@/components/monograph/kinds/place";
import { VIEWS as PLATE_VIEWS } from "@/components/monograph/kinds/plates";
import { VIEWS as SCIENCE_VIEWS } from "@/components/monograph/kinds/science";
import { VIEWS as TOOL_VIEWS } from "@/components/monograph/kinds/tools";
import type { ComponentViews } from "@/lib/componentViewContract";

export const COMPONENT_VIEWS: ComponentViews = {
  ...TOOL_VIEWS,
  ...PLATE_VIEWS,
  ...withDeclared(DATA_VIEWS, { ...DECLARED_VIEWS, related_crafts: KinCraftsView }),
  ...SCIENCE_VIEWS,
  ...BLOCK_VIEWS,
  ...GENERAL_VIEWS,
  ...PLACE_VIEWS
};
