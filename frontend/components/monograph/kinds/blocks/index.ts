import { AnswerBlockView } from "@/components/monograph/kinds/blocks/AnswerBlockView";
import { ANSWER_BLOCK_KIND } from "@/components/monograph/kinds/blocks/answerBlockSpec";
import type { ComponentViews } from "@/lib/componentViewContract";

export const VIEWS: ComponentViews = {
  [ANSWER_BLOCK_KIND]: AnswerBlockView
};
