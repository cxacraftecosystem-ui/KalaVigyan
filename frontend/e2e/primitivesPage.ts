import { readFileSync } from "node:fs";
import { join } from "node:path";

import { FRONTEND } from "./moduleGraph";

const SHEETS = ["tokens.css", "motion.css", "primitives.css", "editorial.css", "editorial-plate.css", "editorial-figure.css", "editorial-monograph.css"];

export const PRIMITIVE_CSS = SHEETS.map((name) => readFileSync(join(FRONTEND, "app", name), "utf8")).join("\n");

export function primitivesPage(body: string, attributes = ""): string {
  return [
    `<!doctype html><html lang="en" ${attributes}><head><meta charset="utf-8"><style>`,
    PRIMITIVE_CSS,
    "*,::before,::after{box-sizing:border-box} body{margin:0;background:var(--ground);color:var(--ink-1);font-family:var(--font-ui)} .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}",
    "</style></head><body>",
    body,
    "</body></html>"
  ].join("");
}
