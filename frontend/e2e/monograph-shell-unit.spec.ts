import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { shellNodes } from "../components/monograph/ShellTree";
import { shellProps, shellStyle } from "../lib/monographShellProps";
import { ShellParseError, shellSlots, shellTree } from "../lib/monographShellTree";

import { REACT_ONLY } from "./monographNative";

const PLATE = "a/b/plate";

const drawn = (html: string) =>
  renderToStaticMarkup(createElement("div", null, ...shellNodes(shellTree(html, new Set([PLATE])), (label) => createElement("figure", { "data-native": label })))).replace(REACT_ONLY, "");

test("the shell keeps every element without a native slot as written and opens only those that hold one", () => {
  const html = `<section class="kv-ch" id="c"><div class="spread"><p class="t-body">One &amp; <i>two</i></p><kv-slot component="${PLATE}"></kv-slot></div><aside class="margin"><b>1</b></aside></section>`;
  const tree = shellTree(html, new Set([PLATE]));
  expect(tree).toEqual([
    {
      kind: "element",
      tag: "section",
      attrs: { class: "kv-ch", id: "c" },
      children: [
        { kind: "element", tag: "div", attrs: { class: "spread" }, children: [{ kind: "held", tag: "p", attrs: { class: "t-body" }, html: "One &amp; <i>two</i>" }, { kind: "slot", label: PLATE }] },
        { kind: "held", tag: "aside", attrs: { class: "margin" }, html: "<b>1</b>" }
      ]
    }
  ]);
  expect(shellSlots(tree)).toEqual([PLATE]);
  expect(drawn(html)).toBe(`<div><section class="kv-ch" id="c"><div class="spread"><p class="t-body">One &amp; <i>two</i></p><figure data-native="${PLATE}"></figure></div><aside class="margin"><b>1</b></aside></section></div>`);
});

test("a slot no native view takes, text, comments, void and raw-text elements are read as a browser reads them", () => {
  const html = `<div id="w">Fish &#x27;n&#39; chips<!-- note --><img src="/a.jpg" alt="A &quot;cloth&quot;"><svg viewBox="0 0 2 2"><path d="M0 0"/></svg><style>.x>.y{color:red}</style><kv-slot component="${PLATE}"></kv-slot><kv-slot component="a/b/other"></kv-slot></div>`;
  expect(drawn(html)).toBe(
    `<div><div id="w">Fish &#x27;n&#x27; chips<img src="/a.jpg" alt="A &quot;cloth&quot;"/><svg viewBox="0 0 2 2"><path d="M0 0"/></svg><style>.x>.y{color:red}</style><figure data-native="${PLATE}"></figure><kv-slot component="a/b/other"></kv-slot></div></div>`
  );
});

test("a shell that closes the wrong element, never closes one or names an unknown entity is refused", () => {
  expect(() => shellTree("<div><p>x</div></p>", new Set())).toThrow(ShellParseError);
  expect(() => shellTree("<section><div>x</div>", new Set())).toThrow(ShellParseError);
  expect(() => shellTree(`<div>x &bogus; y<kv-slot component="${PLATE}"></kv-slot></div>`, new Set([PLATE]))).toThrow(ShellParseError);
});

test("attributes become the props React writes back as the same attributes", () => {
  expect(shellProps("div", { class: "a b", style: "--tone: #fff; background-color: red; -webkit-mask: none; -ms-flex: 1", hidden: "", inert: "", "data-x": "" })).toEqual({
    className: "a b",
    style: { "--tone": "#fff", backgroundColor: "red", WebkitMask: "none", msFlex: "1" },
    hidden: true,
    inert: true,
    "data-x": ""
  });
  expect(shellProps("input", { type: "range", value: "3", checked: "checked", tabindex: "0" })).toEqual({ type: "range", defaultValue: "3", defaultChecked: true, tabIndex: "0" });
  expect(shellProps("svg", { "stroke-width": "2", "xmlns:xlink": "http://www.w3.org/1999/xlink", viewBox: "0 0 1 1", "aria-hidden": "true" })).toEqual({
    strokeWidth: "2",
    xmlnsXlink: "http://www.w3.org/1999/xlink",
    viewBox: "0 0 1 1",
    "aria-hidden": "true"
  });
  expect(shellProps("details", { open: "open" })).toEqual({ open: true });
  expect(shellProps("a", { download: "film.mp4" })).toEqual({ download: "film.mp4" });
  expect(shellStyle("color: red;;  : x; width:")).toEqual({ color: "red" });
});

test("React writes the converted attributes back as the shell wrote them", () => {
  const html = `<div class="a b" style="--tone:#fff;background-color:red" hidden="" inert=""><input type="range" value="3" tabindex="0"><svg viewBox="0 0 1 1" stroke-width="2" xmlns:xlink="http://www.w3.org/1999/xlink"><use href="#x"/></svg><details open=""><summary>S</summary></details><kv-slot component="${PLATE}"></kv-slot></div>`;
  const outer = renderToStaticMarkup(createElement("div", null, ...shellNodes(shellTree(html, new Set([PLATE])), () => null)));
  expect(outer).toContain('<div class="a b" style="--tone:#fff;background-color:red" hidden="" inert="">');
  expect(outer).toMatch(/<input type="range" (value="3" tabindex="0"|tabindex="0" value="3")\/>/);
  expect(outer).toContain('<svg viewBox="0 0 1 1" stroke-width="2" xmlns:xlink="http://www.w3.org/1999/xlink"><use href="#x"/></svg>');
  expect(outer).toContain('<details open=""><summary>S</summary></details>');
});
