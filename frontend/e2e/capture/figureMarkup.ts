const COMMENT = /<!--[\s\S]*?-->/g;
const ID_ATTRIBUTE = /\sid="([^"]*)"/g;
const ATTRIBUTE_VALUE = /(\s[^\s"'>/=]+=")([^"]*)(")/g;
const ID_TOKEN = /[^\s#(),]+/g;
const STYLE_CLOSE = /<\/style/i;

export function withoutComments(markup: string): string {
  return markup.replace(COMMENT, "");
}

export function fixedIds(markup: string, prefix: string): string {
  const ids = [...new Set([...markup.matchAll(ID_ATTRIBUTE)].map((found) => found[1]))];
  const named = new Map(ids.map((id, at) => [id, `${prefix}-${at + 1}`]));
  return markup.replace(ATTRIBUTE_VALUE, (_, open: string, value: string, close: string) => `${open}${value.replace(ID_TOKEN, (token) => named.get(token) ?? token)}${close}`);
}

export function withStyle(markup: string, css: string): string {
  if (STYLE_CLOSE.test(css) || css.includes("<!--")) throw new Error("The figure's styles would close their style element or open a comment");
  const opened = markup.indexOf(">") + 1;
  if (opened <= 0 || !markup.startsWith("<")) throw new Error("The figure's markup does not open with an element");
  return `${markup.slice(0, opened)}<style>${css}</style>${markup.slice(opened)}`;
}

export function figureFragment(outerHtml: string, css: string, idPrefix: string): string {
  return withStyle(fixedIds(withoutComments(outerHtml), idPrefix), css);
}

export function emptyFrame(outerHtml: string, css: string): string {
  const tag = /^<([A-Za-z][\w-]*)/.exec(outerHtml)?.[1];
  if (!tag) throw new Error("The figure's markup does not open with an element");
  return withStyle(`${outerHtml.slice(0, outerHtml.indexOf(">") + 1)}</${tag}>`, css);
}
