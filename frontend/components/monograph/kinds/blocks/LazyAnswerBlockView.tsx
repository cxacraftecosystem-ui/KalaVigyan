"use client";

import { lazyBlock } from "@/components/answer/lazyBlock";
import type { ComponentViewProps } from "@/lib/componentViewContract";

const LazyAnswerBlock = lazyBlock<ComponentViewProps>(() => import("@/components/monograph/kinds/blocks/AnswerBlockView").then((loaded) => loaded.AnswerBlockView), null);

export function LazyAnswerBlockView(props: ComponentViewProps) {
  return <LazyAnswerBlock {...props} />;
}
