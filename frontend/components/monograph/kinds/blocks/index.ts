import { createElement } from "react";

import { lazyBlock } from "@/components/answer/lazyBlock";
import { ANSWER_BLOCK_KIND } from "@/components/monograph/kinds/blocks/answerBlockSpec";
import type { ComponentViewProps, ComponentViews } from "@/lib/componentViewContract";

const LazyAnswerBlock = lazyBlock<ComponentViewProps>(() => import("@/components/monograph/kinds/blocks/AnswerBlockView").then((loaded) => loaded.AnswerBlockView), null);

export const VIEWS: ComponentViews = {
  [ANSWER_BLOCK_KIND]: (props) => createElement(LazyAnswerBlock, props)
};
