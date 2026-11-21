export type PageAudit = {
  pageOverflowPx: number;
  textOverflow: string[];
  alerts: string[];
  copy: string;
};

export type AuditOptions = { citedSelector: string; limit: number };

export function auditPage(options: AuditOptions): PageAudit {
  const root = document.documentElement;
  const viewportWidth = root.clientWidth;
  const flat = (value: string | null) => (value ?? "").replace(/\s+/g, " ").trim();
  const excerpt = (value: string) => (value.length > 60 ? `${value.slice(0, 59)}…` : value);
  const isBox = (element: Element) => !["inline", "contents"].includes(getComputedStyle(element).display);
  const clips = (style: CSSStyleDeclaration) => style.overflowX !== "visible" || style.overflowY !== "visible";
  const shown = (element: Element) => element.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  const name = (element: Element) => {
    const parts: string[] = [];
    for (let node: Element | null = element; node && node !== document.body && parts.length < 3; node = node.parentElement) {
      const testId = node.getAttribute("data-testid");
      const tag = node.tagName.toLowerCase();
      parts.unshift(testId ? `${tag}[data-testid="${testId}"]` : node.id ? `${tag}#${node.id}` : tag);
    }
    return parts.join(" > ");
  };
  const fontPx = (element: Element) => parseFloat(getComputedStyle(element).fontSize) || 16;
  const verticalSlack = (parent: Element, box: Element) => {
    const shifted = parent.closest("sup, sub");
    return shifted && shifted !== box && box.contains(shifted) ? Math.max(2, fontPx(box) * 0.5) : Math.max(2, fontPx(parent) * 0.3);
  };
  const scrolledOrClipped = (element: Element) => {
    for (let node: Element | null = element; node && node !== document.body; node = node.parentElement) {
      if (getComputedStyle(node).overflowX !== "visible") return true;
    }
    return false;
  };

  const textOverflow = new Set<string>();
  const copy: string[] = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = flat(node.textContent);
    const parent = node.parentElement;
    if (!text || !parent || parent.closest("svg, script, style, noscript, template, .katex-mathml") || !shown(parent)) continue;
    if (!parent.closest(options.citedSelector)) copy.push(text);
    if (textOverflow.size >= options.limit) continue;
    let box: Element = parent;
    while (!isBox(box) && box.parentElement) box = box.parentElement;
    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0);
    if (rects.length === 0) continue;
    const slackY = verticalSlack(parent, box);
    const outer = box.getBoundingClientRect();
    const spills = rects.some(
      (rect) => rect.right > outer.right + 2 || rect.left < outer.left - 2 || rect.bottom > outer.bottom + slackY || rect.top < outer.top - slackY
    );
    if (spills && !clips(getComputedStyle(box))) textOverflow.add(`${name(box)}: "${excerpt(text)}" spills out of its box`);
    const offScreen = rects.some((rect) => rect.right > viewportWidth + 2 || rect.left < -2);
    if (offScreen && !scrolledOrClipped(parent)) textOverflow.add(`${name(box)}: "${excerpt(text)}" runs off the screen`);
  }

  const alerts = Array.from(document.querySelectorAll('[role="alert"]'))
    .filter(shown)
    .map((element) => flat(element.textContent))
    .filter(Boolean);

  return {
    pageOverflowPx: Math.max(root.scrollWidth, document.body.scrollWidth) - viewportWidth,
    textOverflow: [...textOverflow],
    alerts,
    copy: copy.join(" ")
  };
}
