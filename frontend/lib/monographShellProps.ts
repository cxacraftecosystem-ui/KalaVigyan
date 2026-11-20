import type { ShellAttributes } from "@/lib/monographShellTree";

const PROP_NAMES: Readonly<Record<string, string>> = {
  class: "className",
  for: "htmlFor",
  tabindex: "tabIndex",
  fetchpriority: "fetchPriority",
  srcset: "srcSet",
  crossorigin: "crossOrigin",
  referrerpolicy: "referrerPolicy",
  colspan: "colSpan",
  rowspan: "rowSpan",
  datetime: "dateTime",
  maxlength: "maxLength",
  minlength: "minLength",
  readonly: "readOnly",
  autoplay: "autoPlay",
  playsinline: "playsInline",
  allowfullscreen: "allowFullScreen",
  contenteditable: "contentEditable",
  spellcheck: "spellCheck",
  accesskey: "accessKey",
  srcdoc: "srcDoc",
  usemap: "useMap",
  enterkeyhint: "enterKeyHint",
  inputmode: "inputMode",
  autocomplete: "autoComplete",
  autofocus: "autoFocus",
  novalidate: "noValidate",
  formnovalidate: "formNoValidate",
  itemscope: "itemScope",
  "xmlns:xlink": "xmlnsXlink",
  "xlink:href": "xlinkHref",
  "xlink:title": "xlinkTitle",
  "xml:space": "xmlSpace",
  "xml:lang": "xmlLang"
};

const SVG_HYPHENATED = new Set([
  "alignment-baseline",
  "baseline-shift",
  "clip-path",
  "clip-rule",
  "color-interpolation",
  "color-interpolation-filters",
  "dominant-baseline",
  "fill-opacity",
  "fill-rule",
  "flood-color",
  "flood-opacity",
  "font-family",
  "font-size",
  "font-style",
  "font-weight",
  "image-rendering",
  "letter-spacing",
  "lighting-color",
  "marker-end",
  "marker-mid",
  "marker-start",
  "paint-order",
  "pointer-events",
  "shape-rendering",
  "stop-color",
  "stop-opacity",
  "stroke-dasharray",
  "stroke-dashoffset",
  "stroke-linecap",
  "stroke-linejoin",
  "stroke-miterlimit",
  "stroke-opacity",
  "stroke-width",
  "text-anchor",
  "text-decoration",
  "text-rendering",
  "vector-effect",
  "word-spacing",
  "writing-mode"
]);

const BOOLEAN = new Set([
  "allowfullscreen",
  "async",
  "autofocus",
  "autoplay",
  "checked",
  "controls",
  "default",
  "defer",
  "disabled",
  "download",
  "formnovalidate",
  "hidden",
  "inert",
  "itemscope",
  "loop",
  "multiple",
  "muted",
  "novalidate",
  "open",
  "playsinline",
  "readonly",
  "required",
  "reversed",
  "selected"
]);

const FORM_FIELDS = new Set(["input", "select", "textarea"]);
const FORM_DEFAULTS: Readonly<Record<string, string>> = { value: "defaultValue", checked: "defaultChecked" };

function camel(name: string): string {
  return name.replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

function styleKey(name: string): string {
  if (name.startsWith("--")) return name;
  const lower = name.toLowerCase();
  return camel(lower.startsWith("-ms-") ? lower.slice(1) : lower);
}

export function shellStyle(css: string): Record<string, string> {
  const style: Record<string, string> = {};
  for (const declaration of css.split(";")) {
    const at = declaration.indexOf(":");
    const name = declaration.slice(0, at).trim();
    const value = declaration.slice(at + 1).trim();
    if (at > 0 && name && value) style[styleKey(name)] = value;
  }
  return style;
}

function propName(tag: string, name: string): string {
  if (FORM_FIELDS.has(tag) && FORM_DEFAULTS[name]) return FORM_DEFAULTS[name];
  if (PROP_NAMES[name]) return PROP_NAMES[name];
  return SVG_HYPHENATED.has(name) ? camel(name) : name;
}

function propValue(name: string, value: string): unknown {
  if (name === "style") return shellStyle(value);
  if (BOOLEAN.has(name) && (value === "" || value.toLowerCase() === name)) return true;
  return value;
}

export function shellProps(tag: string, attrs: ShellAttributes): Record<string, unknown> {
  const lower = tag.toLowerCase();
  return Object.fromEntries(Object.entries(attrs).map(([name, value]) => [propName(lower, name), propValue(name, value)]));
}
