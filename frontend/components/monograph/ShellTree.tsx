import { createElement, Fragment, type ReactNode } from "react";

import { shellProps } from "@/lib/monographShellProps";
import type { ShellNode } from "@/lib/monographShellTree";

export type ShellSlotRenderer = (label: string) => ReactNode;

function shellNode(node: ShellNode, key: number, slot: ShellSlotRenderer): ReactNode {
  if (node.kind === "text") return node.text;
  if (node.kind === "slot") return createElement(Fragment, { key }, slot(node.label));
  const props = { ...shellProps(node.tag, node.attrs), key };
  if (node.kind === "held") return createElement(node.tag, { ...props, dangerouslySetInnerHTML: { __html: node.html } });
  return createElement(node.tag, props, ...shellNodes(node.children, slot));
}

export function shellNodes(nodes: readonly ShellNode[], slot: ShellSlotRenderer): ReactNode[] {
  return nodes.map((node, at) => shellNode(node, at, slot));
}
