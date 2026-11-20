import { VIEWS as BLOCK_VIEWS } from "@/components/monograph/kinds/blocks";
import { VIEWS as DATA_VIEWS } from "@/components/monograph/kinds/data";
import { VIEWS as PLATE_VIEWS } from "@/components/monograph/kinds/plates";
import { VIEWS as SCIENCE_VIEWS } from "@/components/monograph/kinds/science";
import { VIEWS as TOOL_VIEWS } from "@/components/monograph/kinds/tools";
import type { ComponentViews } from "@/lib/componentViewContract";

export const COMPONENT_VIEWS: ComponentViews = {
  ...TOOL_VIEWS,
  ...PLATE_VIEWS,
  ...DATA_VIEWS,
  ...SCIENCE_VIEWS,
  ...BLOCK_VIEWS
};
