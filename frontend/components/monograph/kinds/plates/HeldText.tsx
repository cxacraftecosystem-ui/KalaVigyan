import { createElement, type ReactNode } from "react";

import { clusterName } from "@/lib/citationCluster";
import type { HeldMark, HeldNode, HeldOrUnit, ShownSource } from "@/lib/componentSpecsPlates";

const PLAIN_MARKS = ["b", "sub", "sup", "mark"];

function field(mark: HeldMark, name: string): string | undefined {
  const value = mark[name];
  return typeof value === "string" ? value : undefined;
}

export function CiteButton({ mark }: { mark: HeldMark }) {
  const shown = mark.shown as ShownSource[];
  const keys = mark.g as string[];
  return (
    // eslint-disable-next-line jsx-a11y/role-supports-aria-props -- the approved page's citation button names its sources' titles as its description, as render_nodes writes it
    <button
      className="kcite"
      type="button"
      data-c={field(mark, "key")}
      data-g={keys.join(" ")}
      aria-haspopup="dialog"
      aria-expanded="false"
      aria-label={clusterName(shown)}
      aria-description={shown.map((source) => source.title).join("; ")}
    >
      {shown.map((source) => source.number).join(",")}
    </button>
  );
}

function sentenceClass(mark: HeldMark): string {
  const extra = field(mark, "cls");
  return extra ? `s ${extra}` : "s";
}

function heldMark(mark: HeldMark, key: number): ReactNode {
  const inner = <HeldText nodes={mark.c ?? []} />;
  switch (mark.m) {
    case "s":
      return <span key={key} className={sentenceClass(mark)} data-src={field(mark, "src")} data-sid={field(mark, "sid")} data-pair={field(mark, "pair")}>{inner}</span>;
    case "span":
      return <span key={key} className={field(mark, "cls")}>{inner}</span>;
    case "cite":
      return <span key={key} className="nw">{inner}<CiteButton mark={mark} /></span>;
    case "i":
      return <i key={key} className={field(mark, "role")}>{inner}</i>;
    case "figref":
      return <span key={key} className="kv-figref" data-figref={field(mark, "ref")}>{inner}</span>;
    case "link":
      return field(mark, "cls") ? (
        <a key={key} className={field(mark, "cls")} href={field(mark, "href")}>{inner}</a>
      ) : (
        <a key={key} href={field(mark, "href")} rel={field(mark, "rel")} target={field(mark, "target")} data-ask={field(mark, "ask")} lang={field(mark, "lang")}>{inner}</a>
      );
    default:
      if (PLAIN_MARKS.includes(mark.m)) return createElement(mark.m, { key }, inner);
      throw new RangeError(`No inline mark ${mark.m}`);
  }
}

export function HeldText({ nodes }: { nodes: HeldNode[] }) {
  return <>{nodes.map((node, index) => (typeof node === "string" ? node : heldMark(node, index)))}</>;
}

export function HeldOrUnitText({ value, renderUnit }: { value: HeldOrUnit; renderUnit: (ref: string) => ReactNode }) {
  return typeof value === "string" ? <>{renderUnit(value)}</> : <HeldText nodes={value} />;
}
