import { defineConfig, devices, type Project } from "@playwright/test";

import { ANONYMOUS_WIDTHS, DESKTOP, FAKE_MICROPHONE_ARGS, IPHONE, PHONE, QUESTIONS_SCHEME, QUESTIONS_WIDTH, SCHEMES, SCREEN_WIDTHS, SMALL_PHONE, TABLET, WIDE, anonymousProjectName, contextOptions, projectName, runLabel, type Scheme, type Width } from "./e2e/production/matrix";
import { captureLooks, captureProjectName, type CaptureLook } from "./e2e/capture/captureParts";
import { isPreview, siteRefusal } from "./e2e/production/preview";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const LOCAL = /^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/.test(BASE_URL);
const SMOKE = process.env.E2E_SMOKE === "1";
const PRODUCTION = process.env.E2E_PRODUCTION === "1";
const PARITY = process.env.E2E_PARITY === "1";
const CAPTURE = process.env.E2E_CAPTURE === "1";
const FIGURE = process.env.E2E_FIGURE === "1";
const CAPTURE_SPEC = /[\\/]e2e[\\/]capture[\\/]capture\.spec\.ts$/;
const FIGURE_SPEC = /[\\/]e2e[\\/]capture[\\/]figure\.spec\.ts$/;
const PARITY_SPEC = /[\\/]e2e[\\/]parity[\\/]monograph-parity\.spec\.ts$/;
const PARITY_WIDTHS: readonly Width[] = [SMALL_PHONE, TABLET, DESKTOP];
const CAPTURE_WIDTHS: readonly Width[] = [...PARITY_WIDTHS, WIDE];

const PRODUCTION_SPECS = /[\\/]e2e[\\/]production[\\/]/;
const SCREENS_SPEC = /[\\/]e2e[\\/]production[\\/]screens\.spec\.ts$/;
const QUESTIONS_SPEC = /[\\/]e2e[\\/]production[\\/]questions\.spec\.ts$/;
const ROLES_SPEC = /[\\/]e2e[\\/]production[\\/]roles\.spec\.ts$/;
const ANONYMOUS_SPEC = /[\\/]e2e[\\/]production[\\/]anonymous\.spec\.ts$/;
const VOICE_SPEC = /[\\/]e2e[\\/]production[\\/]voice\.spec\.ts$/;
const VOICE_WIDTHS: readonly Width[] = [DESKTOP, PHONE];

if (PRODUCTION && !process.env.E2E_BASE_URL) throw new Error("E2E_PRODUCTION=1 needs E2E_BASE_URL");
const REFUSED_SITE = PRODUCTION ? siteRefusal(BASE_URL) : null;
if (REFUSED_SITE) throw new Error(REFUSED_SITE);

const RUN_USE = {
  baseURL: BASE_URL,
  screenshot: "off",
  trace: "off",
  video: "off",
  actionTimeout: 30_000
} as const;

function productionProject(width: Width, scheme: Scheme, specs: RegExp[]): Project {
  return {
    name: projectName(width, scheme),
    testMatch: specs,
    retries: 0,
    metadata: { label: runLabel(width, scheme), scheme },
    use: { ...devices[width.device], ...contextOptions(width, scheme), ...RUN_USE }
  };
}

function specsFor(width: Width, scheme: Scheme): RegExp[] {
  return width === QUESTIONS_WIDTH && scheme === QUESTIONS_SCHEME ? [SCREENS_SPEC, QUESTIONS_SPEC, ROLES_SPEC] : [SCREENS_SPEC];
}

function anonymousProject(width: Width): Project {
  return {
    name: anonymousProjectName(width),
    testMatch: [ANONYMOUS_SPEC],
    retries: 0,
    metadata: { label: `${width.label} signed out`, scheme: "light" },
    use: { ...devices[width.device], ...contextOptions(width, "light"), ...RUN_USE }
  };
}

function pageProject(prefix: string, spec: RegExp, width: Width, scheme: Scheme): Project {
  return {
    name: `${prefix}-${width.key}-${scheme}`,
    testMatch: [spec],
    retries: 0,
    use: { ...devices[width.device], ...contextOptions(width, scheme), ...RUN_USE }
  };
}

const PARITY_PROJECTS: Project[] = PARITY_WIDTHS.flatMap((width) => SCHEMES.map((scheme) => pageProject("parity", PARITY_SPEC, width, scheme)));
const FIGURE_PROJECTS: Project[] = PARITY_WIDTHS.flatMap((width) => SCHEMES.map((scheme) => pageProject("figure", FIGURE_SPEC, width, scheme)));

function captureProject(width: Width, look: CaptureLook): Project {
  const contrast = look.contrast ? { contrast: "more" as const } : {};
  return { name: captureProjectName(width.key, look), testMatch: [CAPTURE_SPEC], retries: 0, use: { ...devices[width.device], ...contextOptions(width, look.scheme), ...contrast, ...RUN_USE } };
}

const CAPTURE_PROJECTS: Project[] = CAPTURE_WIDTHS.flatMap((width) => captureLooks(width.key, SMALL_PHONE.key).map((look) => captureProject(width, look)));

function voiceProject(width: Width, scheme: Scheme): Project {
  return {
    name: `production-voice-${width.key}-${scheme}`,
    testMatch: [VOICE_SPEC],
    retries: 0,
    metadata: { label: `${runLabel(width, scheme)} voice dock`, scheme },
    use: { ...devices[width.device], ...contextOptions(width, scheme), ...RUN_USE, permissions: ["microphone"], launchOptions: { args: FAKE_MICROPHONE_ARGS } }
  };
}

const PRODUCTION_PROJECTS: Project[] = [
  ...SCREEN_WIDTHS.flatMap((width) => SCHEMES.map((scheme) => productionProject(width, scheme, specsFor(width, scheme)))),
  ...ANONYMOUS_WIDTHS.map(anonymousProject),
  ...VOICE_WIDTHS.flatMap((width) => SCHEMES.map((scheme) => voiceProject(width, scheme))),
  ...(isPreview(BASE_URL) ? [productionProject(IPHONE, "light", [SCREENS_SPEC])] : [])
];

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: Number(process.env.E2E_WORKERS ?? 2),
  retries: Number(process.env.E2E_RETRIES ?? 0),
  reporter: [["list"]],
  globalSetup: SMOKE && LOCAL ? "./e2e/smokeApi.ts" : undefined,
  globalTeardown: PRODUCTION ? "./e2e/production/teardown.ts" : undefined,
  use: {
    baseURL: BASE_URL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure"
  },
  projects: [
    { name: "unit", testMatch: /-unit\.spec\.ts$/, testIgnore: PRODUCTION_SPECS },
    { name: "desktop", testMatch: /smoke\.spec\.ts$/, testIgnore: PRODUCTION_SPECS, use: { ...devices["Desktop Chrome"] } },
    { name: "phone", testMatch: /smoke\.spec\.ts$/, testIgnore: PRODUCTION_SPECS, use: { ...devices["Pixel 7"] } },
    ...(PRODUCTION ? PRODUCTION_PROJECTS : []),
    ...(PARITY ? PARITY_PROJECTS : []),
    ...(CAPTURE ? CAPTURE_PROJECTS : []),
    ...(FIGURE ? FIGURE_PROJECTS : [])
  ],
  webServer:
    SMOKE && LOCAL
      ? {
          command: "npm run start",
          url: BASE_URL,
          reuseExistingServer: false,
          timeout: 120_000
        }
      : undefined
});
