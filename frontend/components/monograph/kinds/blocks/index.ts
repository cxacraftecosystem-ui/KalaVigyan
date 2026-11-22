import { ANSWER_BLOCK_KIND } from "@/components/monograph/kinds/blocks/answerBlockSpec";
import { LazyAnswerBlockView } from "@/components/monograph/kinds/blocks/LazyAnswerBlockView";
import type { ComponentViews } from "@/lib/componentViewContract";

export const VIEWS: ComponentViews = {
  [ANSWER_BLOCK_KIND]: LazyAnswerBlockView
};
