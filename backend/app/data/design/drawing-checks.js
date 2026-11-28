(() => {
  const LIMITS = Object.freeze({ iconView: 32, iconLeast: 8, iconWidth: 64, figureText: 96, svgText: 48 });
  const NODE_CAP = 500;
  const PROBLEMS_MAX = 12;
  const PAGE_PROBLEMS_MAX = 60;
  const TOLERANCE_PX = 2;
  const PAGE = "page";
  const SCROLL_PAUSE_MS = 40;
  const SCROLL_STEPS_MAX = 240;
  const SHAPES = ["path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "image", "use"];
  const PICTURES = ["canvas", "img", "video"];
  const GRAPHICS = "svg, img, canvas, video, picture";
  const HEADINGS = "h2, h3, h4, h5, h6, [role='heading']";
  const CLIPPING = new Set(["hidden", "auto", "scroll", "clip"]);
  const DRAWN_ROLES = new Set(["picture", "chart", "map", "interactive"]);
  const UNCOLOURED = "[data-kit-uncoloured]";
  const AT_REST_ROLES = new Set(["chart", "map", "interactive"]);

  function componentProblems(element) {
    const problems = [];
    const box = element.getBoundingClientRect();
    if (box.height < 1 || box.width < 1) problems.push(`draws ${Math.round(box.width)} by ${Math.round(box.height)}`);
    for (const svg of element.querySelectorAll("svg")) {
      const view = svg.viewBox?.baseVal;
      const width = svg.getBoundingClientRect().width;
      if (view && view.width >= LIMITS.iconLeast && view.width <= LIMITS.iconView && width > LIMITS.iconWidth) problems.push(`an icon of ${view.width} units draws ${Math.round(width)}px wide`);
    }
    const uncoloured = element.querySelectorAll(UNCOLOURED).length;
    if (uncoloured) problems.push(`draws ${uncoloured} species with no colour, each an empty outline in its scene: give each its material or its mark (clear, gas or ion)`);
    for (const node of element.querySelectorAll("*")) {
      const size = parseFloat(getComputedStyle(node).fontSize);
      const height = node.getBoundingClientRect().height;
      const shown = height > 0 && node.textContent?.trim();
      if (shown && size > LIMITS.figureText) problems.push(`${node.tagName.toLowerCase()} text draws at ${Math.round(size)}px`);
      if (shown && node.tagName.toLowerCase() === "text" && height > LIMITS.svgText) problems.push(`an SVG label draws ${Math.round(height)}px tall`);
    }
    return [...new Set(problems)].slice(0, PROBLEMS_MAX);
  }

  function shown(node) {
    const style = getComputedStyle(node);
    return style.display !== "none" && style.visibility !== "hidden";
  }

  function sized(node) {
    const box = node.getBoundingClientRect();
    return box.width >= 1 && box.height >= 1;
  }

  function visible(node) {
    return sized(node) && shown(node);
  }

  function nodesOf(element) {
    return [...element.querySelectorAll("*")].slice(0, NODE_CAP);
  }

  function clipped(node, root) {
    for (let at = node.parentElement; at && at !== root.parentElement; at = at.parentElement) {
      if (CLIPPING.has(getComputedStyle(at).overflowX)) return true;
    }
    return false;
  }

  function overflows(element, view) {
    const box = element.getBoundingClientRect();
    const problems = [];
    if (box.right - view > TOLERANCE_PX) problems.push(`runs ${Math.round(box.right - view)}px past the ${view}px screen`);
    let widest = null;
    for (const node of nodesOf(element)) {
      const over = node.getBoundingClientRect().right - box.right;
      if (over <= TOLERANCE_PX || !visible(node) || clipped(node, element)) continue;
      if (!widest || over > widest.over) widest = { tag: node.tagName.toLowerCase(), over };
    }
    if (widest) problems.push(`a ${widest.tag} runs ${Math.round(widest.over)}px past its column`);
    return problems;
  }

  function loaded(image) {
    return image.complete && image.naturalWidth > 0;
  }

  function drawsSomething(element) {
    if ((element.innerText ?? "").trim()) return true;
    return [...element.querySelectorAll(GRAPHICS)].some(visible);
  }

  function isGraphic(node) {
    const tag = node.tagName.toLowerCase();
    if (SHAPES.includes(tag)) {
      const box = node.getBoundingClientRect();
      return shown(node) && (box.width >= 1 || box.height >= 1);
    }
    return PICTURES.includes(tag) && visible(node) && (tag !== "img" || loaded(node));
  }

  function filled(node) {
    if (node.children.length || (node.textContent ?? "").trim() || !shown(node)) return false;
    const fill = getComputedStyle(node).backgroundColor;
    return fill !== "transparent" && !/^rgba\(.*,\s*0\)$/.test(fill);
  }

  function isBar(node) {
    return sized(node) && filled(node);
  }

  function marks(element, role) {
    return nodesOf(element).filter((node) => isGraphic(node) || (role === "chart" && isBar(node))).length;
  }

  function flatBars(element) {
    return nodesOf(element).filter((node) => {
      const box = node.getBoundingClientRect();
      return box.height >= 1 && box.width < 1 && filled(node);
    }).length;
  }

  function outsideProblems(element) {
    for (const node of nodesOf(element)) {
      if (getComputedStyle(node).position !== "absolute" || !visible(node)) continue;
      const holder = node.offsetParent;
      if (holder && !element.contains(holder)) return [`a ${node.tagName.toLowerCase()} is drawn against the page outside its slot, so the slot does not hold its height`];
    }
    return [];
  }

  function moving(element) {
    if (typeof element.getAnimations !== "function") return 0;
    return element.getAnimations({ subtree: true }).filter((animation) => animation.playState === "running").length;
  }

  function busy(element) {
    return element.matches("[aria-busy='true']") || element.querySelector("[aria-busy='true']") !== null;
  }

  function pictureProblems(element) {
    const images = [...element.querySelectorAll("img")].filter(shown);
    if (!images.length) return ["draws no picture"];
    return images.some(loaded) ? [] : ["its picture did not load"];
  }

  function restProblems(element, role) {
    const problems = [];
    if (busy(element)) problems.push("is still loading at rest");
    const running = moving(element);
    if (running) problems.push(`still moves at rest (${running} animations running)`);
    if (role === "map" && !marks(element, role)) problems.push("draws no map");
    if (role === "chart" && !marks(element, role)) {
      const flat = flatBars(element);
      problems.push(flat ? `draws no marks: its ${flat} bars draw 0px wide` : "draws no marks");
    }
    return problems;
  }

  function slotOf(label) {
    return document.querySelector(`[data-component="${CSS.escape(label)}"]`);
  }

  function drawnProblems(element, component, view) {
    const problems = [...componentProblems(element)];
    if (component.role === "picture") problems.push(...pictureProblems(element));
    else if (!drawsSomething(element)) problems.push("draws empty");
    if (AT_REST_ROLES.has(component.role)) problems.push(...restProblems(element, component.role));
    problems.push(...outsideProblems(element));
    problems.push(...overflows(element, view));
    return [...new Set(problems)].slice(0, PROBLEMS_MAX);
  }

  function componentReview(component, view) {
    const element = slotOf(component.label);
    if (!element) return component.placed && DRAWN_ROLES.has(component.role) ? ["is placed in the layout but the page does not draw it"] : [];
    return drawnProblems(element, component, view);
  }

  function words(text) {
    return (text ?? "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  function headlineProblems(height) {
    const headlines = [...document.querySelectorAll("h1")].filter(visible);
    if (!headlines.length) return ["draws no headline (h1) with the page's name"];
    const problems = headlines.length > 1 ? [`draws ${headlines.length} headlines (h1); the name is its one headline`] : [];
    const first = headlines[0];
    const top = Math.round(first.getBoundingClientRect().top);
    if (top >= height) problems.push(`its name (the h1) starts ${top}px down, below the first ${height}px`);
    const name = words(first.innerText);
    const again = [...document.querySelectorAll(HEADINGS)].filter((node) => visible(node) && node.getBoundingClientRect().top < height && words(node.innerText) === name);
    if (again.length) problems.push(`the first ${height}px draw its name again in ${again.length} more heading${again.length > 1 ? "s" : ""}`);
    return problems;
  }

  function mastheadProblems(label, height) {
    const slot = slotOf(label);
    const image = slot && [...slot.querySelectorAll("img")].find(visible);
    if (!image) return ["the masthead picture is not drawn"];
    if (!loaded(image)) return ["the masthead picture did not load"];
    const top = Math.round(image.getBoundingClientRect().top);
    return top >= height ? [`the masthead picture starts ${top}px down, below the first ${height}px`] : [];
  }

  function firstScreen(plan) {
    window.scrollTo(0, 0);
    const height = window.innerHeight;
    const width = window.innerWidth;
    const found = headlineProblems(height).map((problem) => ({ label: PAGE, problem }));
    if (plan.masthead) found.push(...mastheadProblems(plan.masthead, height).map((problem) => ({ label: plan.masthead, problem })));
    const wider = document.documentElement.scrollWidth - width;
    if (wider > TOLERANCE_PX) found.push({ label: PAGE, problem: `is ${wider}px wider than the ${width}px screen, so it scrolls sideways` });
    return found;
  }

  function chapters(keys) {
    return keys
      .map((key) => {
        const element = document.getElementById(key);
        if (!element || !visible(element)) return null;
        const box = element.getBoundingClientRect();
        return { key, top: Math.round(box.top + window.scrollY), height: Math.round(box.height) };
      })
      .filter(Boolean);
  }

  function review(plan) {
    const found = firstScreen(plan);
    const view = window.innerWidth;
    for (const component of plan.components) {
      for (const problem of componentReview(component, view)) found.push({ label: component.label, problem });
    }
    window.scrollTo(0, 0);
    return { problems: found.slice(0, PAGE_PROBLEMS_MAX), chapters: chapters(plan.chapters), height: document.documentElement.scrollHeight };
  }

  function pause(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function settled(image) {
    return new Promise((resolve) => {
      image.addEventListener("load", resolve, { once: true });
      image.addEventListener("error", resolve, { once: true });
    });
  }

  async function settle(most) {
    const step = Math.max(200, Math.floor(window.innerHeight * 0.9));
    for (let y = 0, at = 0; y < document.documentElement.scrollHeight && at < SCROLL_STEPS_MAX; y += step, at += 1) {
      window.scrollTo(0, y);
      await pause(SCROLL_PAUSE_MS);
    }
    window.scrollTo(0, 0);
    const images = [...document.images];
    for (const image of images) image.loading = "eager";
    const pending = images.filter((image) => !image.complete).map(settled);
    await Promise.race([Promise.all([...pending, document.fonts.ready]), pause(most)]);
    return pending.length;
  }

  globalThis.kvDrawing = Object.freeze({ limits: LIMITS, componentProblems, review, settle, chapters });
})();
