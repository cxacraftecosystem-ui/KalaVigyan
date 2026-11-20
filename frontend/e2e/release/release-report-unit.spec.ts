import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { checkRecord, keepRecord, pathFileName, readRecords, recordFileName, summaryMarkdown, writeSummary } from "./report";

test("a record passes exactly when it names no problem", () => {
  expect(checkRecord("page", "Map (/map)", [])).toEqual({ check: "page", target: "Map (/map)", subject: null, variant: null, ok: true, problems: [], notes: [], numbers: {} });
  expect(checkRecord("axe", "/map at axe-desktop-dark", [], { subject: "/map", variant: "axe-desktop-dark" })).toMatchObject({ subject: "/map", variant: "axe-desktop-dark" });
  expect(checkRecord("page", "Map (/map)", ["the page answered 500; it should answer 200"]).ok).toBe(false);
});

test("record and report files are named from what they hold, with nothing unsafe in the name", () => {
  expect(recordFileName({ check: "page", target: "Kutch Ajrakh (/crafts/Kutch-Ajrakh)" })).toBe("page-Kutch_Ajrakh_crafts_Kutch-Ajrakh.json");
  expect(pathFileName("/", "json")).toBe("landing.json");
  expect(pathFileName("/compare?crafts=Kutch-Ajrakh&crafts=Bagru-Hand-Block-Print", "lighthouse")).toBe("compare_crafts_Kutch-Ajrakh_crafts_Bagru-Hand-Block-Print.lighthouse");
});

test("the summary counts the checks and failures and lists each outcome and measurement in a table", () => {
  const markdown = summaryMarkdown("Post-deploy check", [
    checkRecord("page", "Map (/map)", []),
    checkRecord("lighthouse", "/ at 360 (mobile)", ["performance scores 41; the budget is 50"], { numbers: { performance: 41, cls: null } }),
    checkRecord("axe", "/login at axe-desktop-dark", [], { notes: ["region (moderate) on 2"] })
  ]);
  expect(markdown).toBe(
    [
      "## Post-deploy check",
      "",
      "3 checks, 1 failed.",
      "",
      "| Check | Target | Outcome | Measured |",
      "|---|---|---|---|",
      "| page | Map (/map) | passed |  |",
      "| lighthouse | / at 360 (mobile) | failed: performance scores 41; the budget is 50 | performance 41, cls none |",
      "| axe | /login at axe-desktop-dark | passed (region (moderate) on 2) |  |",
      ""
    ].join("\n")
  );
});

test("a pipe in a problem does not break the table", () => {
  expect(summaryMarkdown("Checks", [checkRecord("mcp", "tools/list", ["a | b"])])).toContain("| failed: a \\| b |");
});

test("records kept by separate tests are read back in name order and summarised into one file", () => {
  const dir = mkdtempSync(join(tmpdir(), "kv-release-report-"));
  try {
    keepRecord(checkRecord("page", "Sign in (/login)", []), dir);
    keepRecord(checkRecord("mcp", "initialize", ["the server answered HTTP 502: bad gateway"]), dir);
    expect(readRecords(dir).map((record) => record.target)).toEqual(["initialize", "Sign in (/login)"]);
    writeSummary("Release checks", dir);
    expect(readFileSync(join(dir, "summary.md"), "utf8")).toContain("2 checks, 1 failed.");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a run that wrote no record says so", () => {
  expect(summaryMarkdown("Release checks", [])).toBe(["## Release checks", "", "0 checks, 0 failed.", "", "No check wrote a record.", ""].join("\n"));
});
