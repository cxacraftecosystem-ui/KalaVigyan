import {
  complexSelectors,
  declaredNames,
  isRootCompound,
  layerOrder,
  matchingForm,
  nestedCss,
  rootScopedSelector,
  scopedSelector,
  structuralSelectors,
  varNames,
  type Declared,
  type PlacedRule,
  type SheetRead,
  type StyleEntry
} from "./figureCss";

export type FigureStyles = { css: string; vars: string[]; matched: number; tokens: number; properties: number; structural: string[] };
export type ComputedProps = Readonly<Record<string, string>>;

export type TokenRule = { at: number; entry: StyleEntry; roots: string[] };
type Placed = { at: number; rule: PlacedRule };

function declarations(vars: readonly Declared[]): string {
  return vars.map(([name, value, priority]) => `${name}: ${value}${priority ? ` !${priority}` : ""};`).join(" ");
}

function styleEntries(read: SheetRead): { at: number; entry: StyleEntry }[] {
  return read.entries.flatMap((entry, at) => (entry.kind === "style" && entry.sheet !== read.kit ? [{ at, entry }] : []));
}

function matchedRules(read: SheetRead, matched: ReadonlySet<string>, scope: string): Placed[] {
  return styleEntries(read).flatMap(({ at, entry }) => {
    const kept = complexSelectors(entry.selector).filter((selector) => matched.has(matchingForm(selector)));
    if (!kept.length || !entry.body.trim()) return [];
    return [{ at, rule: { chain: entry.chain, text: `${kept.map((selector) => scopedSelector(selector, scope)).join(", ")} { ${entry.body} }` } }];
  });
}

function tokenRules(read: SheetRead): TokenRule[] {
  return styleEntries(read).flatMap(({ at, entry }) => {
    const roots = complexSelectors(entry.selector).filter(isRootCompound);
    return roots.length && entry.vars.length ? [{ at, entry, roots }] : [];
  });
}

export function kitTokenNames(read: SheetRead): Set<string> {
  const kit = read.entries.filter((entry): entry is StyleEntry => entry.kind === "style" && entry.sheet === read.kit && complexSelectors(entry.selector).some(isRootCompound));
  return new Set(kit.flatMap((entry) => entry.vars.map(([name]) => name)));
}

export function kitPropertyNames(read: SheetRead): Set<string> {
  const kit = read.entries.filter((entry) => entry.sheet === read.kit);
  return new Set(kit.flatMap((entry) => (entry.kind === "property" ? [entry.name] : [...varNames(entry.body), ...declaredNames(entry.body)])));
}

function registeredProperties(read: SheetRead, declared: ReadonlySet<string>): string[] {
  const kit = kitPropertyNames(read);
  return read.entries.flatMap((entry) => (entry.kind === "property" && entry.sheet !== read.kit && declared.has(entry.name) && !kit.has(entry.name) ? [entry.text] : []));
}

function shadowedByKit(read: SheetRead, kitNames: ReadonlySet<string>, entry: StyleEntry, name: string): boolean {
  return read.kit >= 0 && entry.sheet < read.kit && kitNames.has(name);
}

export function referencedVars(seed: readonly string[], tokens: readonly TokenRule[], shadowed: (entry: StyleEntry, name: string) => boolean): Set<string> {
  const names = new Set(seed.flatMap(varNames));
  let grown = true;
  while (grown) {
    grown = false;
    for (const { entry } of tokens) {
      for (const [name, value] of entry.vars) {
        if (!names.has(name) || shadowed(entry, name)) continue;
        for (const used of varNames(value).filter((found) => !names.has(found))) {
          names.add(used);
          grown = true;
        }
      }
    }
  }
  return names;
}

function placedTokens(tokens: readonly TokenRule[], names: ReadonlySet<string>, shadowed: (entry: StyleEntry, name: string) => boolean, scope: string): Placed[] {
  return tokens.flatMap(({ at, entry, roots }) => {
    const kept = entry.vars.filter(([name]) => names.has(name) && !shadowed(entry, name));
    return kept.length ? [{ at, rule: { chain: entry.chain, text: `${roots.map((root) => rootScopedSelector(root, scope)).join(", ")} { ${declarations(kept)} }` } }] : [];
  });
}

export function figureStyles(read: SheetRead, matched: ReadonlySet<string>, markup: string, scope: string): FigureStyles {
  const kitNames = kitTokenNames(read);
  const shadowed = (entry: StyleEntry, name: string) => shadowedByKit(read, kitNames, entry, name);
  const kept = matchedRules(read, matched, scope);
  const tokens = tokenRules(read);
  const names = referencedVars([markup, ...kept.map((placed) => placed.rule.text)], tokens, shadowed);
  const values = placedTokens(tokens, names, shadowed, scope);
  const rules = [...kept, ...values].sort((a, b) => a.at - b.at).map((placed) => placed.rule);
  const declared = new Set([...names, ...rules.flatMap((rule) => declaredNames(rule.text))]);
  const properties = registeredProperties(read, declared);
  const css = [layerOrder(rules, read.layers), ...properties, nestedCss(rules)].filter(Boolean).join("\n");
  return { css, vars: [...names].sort(), matched: kept.length, tokens: values.length, properties: properties.length, structural: structuralSelectors(kept.map((placed) => placed.rule), scope) };
}

export function inheritedResidue(drawn: ComputedProps, parent: ComputedProps, probe: ComputedProps): Record<string, string> {
  return Object.fromEntries(Object.entries(drawn).filter(([name, value]) => parent[name] === value && probe[name] !== value));
}

export function residueRule(residue: ComputedProps, scope: string): string {
  const declared = Object.entries(residue).map(([name, value]) => `${name}: ${value};`);
  return declared.length ? `:where(${scope}) { ${declared.join(" ")} }` : "";
}
