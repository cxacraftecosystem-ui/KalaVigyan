type Token = (name: string) => string;

const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const;

function byShade(c: Token, names: readonly string[]): Record<number, string> {
  return Object.fromEntries(SHADES.map((shade, index) => [shade, c(names[index])]));
}

function oneShade(value: string): Record<number, string> {
  return Object.fromEntries(SHADES.map((shade) => [shade, value]));
}

function tinted(c: Token, strong: string, wash: string): Record<number, string> {
  return byShade(c, [wash, wash, wash, strong, strong, strong, strong, strong, wash, wash, wash]);
}

export function retiredColors(c: Token) {
  return {
    evidence: tinted(c, "success", "success-wash")
  };
}

export function retiredUtilityColors(c: Token) {
  return {
    textColor: {
      purple: byShade(c, ["on-indigo", "ink-2", "indigo-hover", "indigo", "indigo", "indigo", "indigo", "indigo", "indigo-hover", "indigo-hover", "on-indigo"]),
      evidence: oneShade(c("success")),
      red: oneShade(c("error"))
    },
    backgroundColor: {
      purple: byShade(c, ["sunk", "sunk", "turmeric-wash", "indigo", "indigo", "indigo", "indigo", "indigo", "indigo-hover", "sunk", "sunk"])
    },
    borderColor: {
      purple: byShade(c, ["rule-strong", "rule-strong", "rule-strong", "rule-strong", "indigo", "indigo", "indigo", "indigo", "rule-strong", "rule-strong", "rule-strong"]),
      evidence: oneShade(c("success"))
    }
  };
}
