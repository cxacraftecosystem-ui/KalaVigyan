import type { CSSProperties, ReactNode } from "react";

import type { ComponentHome as Home, FrameStep } from "@/lib/monographScopes";

const PASS_THROUGH: CSSProperties = { display: "contents" };
export const HOME_SPACING = "my-12";

export type FragmentHost = { id: string; html: string };

type HomeProps = { home: Home; label: string; kind: string; fragment?: FragmentHost; children?: ReactNode };

function stepProps(step: FrameStep): { className?: string; style?: CSSProperties } {
  return { className: step.classes.length ? step.classes.join(" ") : undefined, style: step.box ? undefined : PASS_THROUGH };
}

function nested(steps: readonly FrameStep[], inner: ReactNode): ReactNode {
  return steps.reduceRight<ReactNode>((child, step) => <div {...stepProps(step)}>{child}</div>, inner);
}

function hosted(steps: readonly FrameStep[], fragment: FragmentHost): ReactNode {
  const last = steps[steps.length - 1];
  const host = last ? stepProps(last) : { style: PASS_THROUGH };
  const inner = <div {...host} id={fragment.id} dangerouslySetInnerHTML={{ __html: fragment.html }} />;
  return nested(steps.slice(0, -1), inner);
}

export function ComponentHome({ home, label, kind, fragment, children }: HomeProps) {
  return (
    <div className={home.scope ? `bx bx-${home.scope} ${HOME_SPACING}` : HOME_SPACING} data-component={label} data-component-kind={kind} data-home={home.source}>
      {fragment ? hosted(home.frame, fragment) : nested(home.frame, children)}
    </div>
  );
}
