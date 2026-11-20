import { expect, test } from "@playwright/test";

import { AUDIT_BASELINE, baselineCandidate, checkedBaseline, recordedAxe, recordedLighthouse, type AuditBaseline } from "./auditBaseline";
import { auditPaths } from "./keyPages";
import { checkRecord } from "./report";

const HOME_MOBILE = { performance: 73, accessibility: 100, "best-practices": 100, lcpMs: 6787, cls: 0.093, tbtMs: 146, bytes: 1_544_239 };

const BASELINE: AuditBaseline = {
  schemaVersion: 1,
  site: "https://kalavigyan.vercel.app",
  recordedAt: "2026-11-20",
  run: 1,
  lighthouse: { "/": { mobile: HOME_MOBILE } },
  axe: { "/crafts/Kutch-Ajrakh": { "label-content-name-mismatch": 121, "target-size": 44 }, "/login": {}, "/map": {} }
};

const META = { site: "https://kalavigyan-abc123def-cxacraftecosystem-8028s-projects.vercel.app", recordedAt: "2026-11-21", run: 2 };

function lighthouse(path: string, form: string, numbers: Record<string, number>) {
  return checkRecord("lighthouse", `${path} at ${form}`, [], { subject: path, variant: form, numbers });
}

function axe(path: string, project: string, numbers: Record<string, number>) {
  return checkRecord("axe", `${path} at ${project}`, [], { subject: path, variant: project, numbers });
}

test("every page audited by default has a recorded Lighthouse run at both widths and a recorded axe run", () => {
  for (const path of auditPaths("")) {
    expect(recordedLighthouse(path, "mobile"), path).toBeDefined();
    expect(recordedLighthouse(path, "desktop"), path).toBeDefined();
    expect(recordedAxe(path), path).toBeDefined();
  }
  expect(AUDIT_BASELINE.schemaVersion).toBe(1);
});

test("a baseline of another schema or without its tables is refused", () => {
  expect(() => checkedBaseline({ schemaVersion: 2, lighthouse: {}, axe: {} })).toThrow(/schema 1/);
  expect(() => checkedBaseline({ schemaVersion: 1, lighthouse: {} })).toThrow(/lighthouse and an axe table/);
});

test("the candidate re-records the noisy timings as measured, keeps the better of each steady number and records new pages as measured", () => {
  const records = [
    lighthouse("/", "mobile", { performance: 70, accessibility: 100, "best-practices": 96, lcpMs: 7000, cls: 0.05, tbtMs: 100, bytes: 1_600_000 }),
    lighthouse("/new", "desktop", { performance: 91, accessibility: 98, "best-practices": 100, lcpMs: 900, cls: 0, tbtMs: 0, bytes: 900_000 })
  ];
  const candidate = baselineCandidate(BASELINE, records, META);
  expect(candidate.lighthouse["/"]?.mobile).toEqual({ performance: 70, accessibility: 100, "best-practices": 100, lcpMs: 7000, cls: 0.05, tbtMs: 100, bytes: 1_544_239 });
  expect(candidate.lighthouse["/new"]?.desktop).toEqual({ performance: 91, accessibility: 98, "best-practices": 100, lcpMs: 900, cls: 0, tbtMs: 0, bytes: 900_000 });
  expect(candidate).toMatchObject({ schemaVersion: 1, ...META });
});

test("the candidate lowers recorded axe counts to the worst project measured, drops fixed rules and never accepts a new rule on a recorded page", () => {
  const records = [
    axe("/crafts/Kutch-Ajrakh", "axe-desktop-light", { "label-content-name-mismatch": 110, "target-size": 44, "color-contrast": 2 }),
    axe("/crafts/Kutch-Ajrakh", "axe-small-phone-dark", { "label-content-name-mismatch": 106, "target-size": 40 }),
    axe("/map", "axe-desktop-light", {}),
    axe("/new", "axe-desktop-light", { "color-contrast": 3 })
  ];
  const candidate = baselineCandidate(BASELINE, records, META);
  expect(candidate.axe).toEqual({
    "/crafts/Kutch-Ajrakh": { "label-content-name-mismatch": 110, "target-size": 44 },
    "/login": {},
    "/map": {},
    "/new": { "color-contrast": 3 }
  });
  expect(baselineCandidate(BASELINE, [axe("/crafts/Kutch-Ajrakh", "axe-desktop-light", { "target-size": 30 })], META).axe["/crafts/Kutch-Ajrakh"]).toEqual({ "target-size": 30 });
});
