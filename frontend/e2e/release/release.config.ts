import { resolve } from "node:path";

import { defineConfig, devices, type Project } from "@playwright/test";

import { DESKTOP, SCHEMES, SMALL_PHONE, contextOptions, type Scheme, type Width } from "../production/matrix";
import { PRODUCTION_ORIGIN } from "../production/preview";

import { reportDir } from "./report";

const AUDIT_WIDTHS: readonly Width[] = [SMALL_PHONE, DESKTOP];

const RUN_USE = {
  baseURL: process.env.E2E_BASE_URL || PRODUCTION_ORIGIN,
  screenshot: "only-on-failure",
  trace: "off",
  video: "off",
  actionTimeout: 30_000
} as const;

function browserProject(name: string, spec: RegExp, width: Width, scheme: Scheme): Project {
  return { name, testMatch: [spec], use: { ...devices[width.device], ...contextOptions(width, scheme), ...RUN_USE } };
}

export default defineConfig({
  testDir: ".",
  testIgnore: /-unit\.spec\.ts$/,
  outputDir: resolve(reportDir(), "test-results"),
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  workers: Number(process.env.E2E_WORKERS ?? 2),
  retries: 0,
  reporter: [["list"]],
  globalTeardown: "./summary.ts",
  projects: [
    browserProject("post-deploy", /post-deploy\.spec\.ts$/, DESKTOP, "light"),
    browserProject("mcp-client", /mcp-client\.spec\.ts$/, DESKTOP, "light"),
    ...AUDIT_WIDTHS.flatMap((width) => SCHEMES.map((scheme) => browserProject(`axe-${width.key}-${scheme}`, /axe\.spec\.ts$/, width, scheme))),
    { name: "lighthouse", testMatch: [/lighthouse\.spec\.ts$/], use: RUN_USE }
  ]
});
