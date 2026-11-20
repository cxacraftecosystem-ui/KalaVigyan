import { expect, test } from "@playwright/test";

import { GET } from "@/app/api/version/route";

type Version = { commit: string | null; ref: string | null; environment: string | null; builtAt: string };

const NAMES = ["VERCEL_GIT_COMMIT_SHA", "GITHUB_SHA", "VERCEL_GIT_COMMIT_REF", "VERCEL_ENV"] as const;
const COMMIT = "5c73b60f0b659fddf244b4e8212e3767edda288c";
const OTHER_COMMIT = "19c7b3ab0680e38f21550fec8b77de60317b3a26";

let saved: Partial<Record<(typeof NAMES)[number], string>> = {};

test.beforeEach(() => {
  saved = {};
  for (const name of NAMES) {
    saved[name] = process.env[name];
    delete process.env[name];
  }
});

test.afterEach(() => {
  for (const name of NAMES) {
    if (saved[name] === undefined) delete process.env[name];
    else process.env[name] = saved[name];
  }
});

async function version(): Promise<Version> {
  return (await GET().json()) as Version;
}

test("the version names the commit, branch and environment Vercel built", async () => {
  process.env.VERCEL_GIT_COMMIT_SHA = COMMIT;
  process.env.VERCEL_GIT_COMMIT_REF = "main";
  process.env.VERCEL_ENV = "production";
  expect(await version()).toMatchObject({ commit: COMMIT, ref: "main", environment: "production" });
});

test("a commit Vercel names in capitals is reported in lowercase", async () => {
  process.env.VERCEL_GIT_COMMIT_SHA = COMMIT.toUpperCase();
  expect((await version()).commit).toBe(COMMIT);
});

test("without Vercel's commit the version names the commit the CI build came from", async () => {
  process.env.GITHUB_SHA = OTHER_COMMIT;
  expect((await version()).commit).toBe(OTHER_COMMIT);
});

test("Vercel's commit wins over the CI commit when both are set", async () => {
  process.env.VERCEL_GIT_COMMIT_SHA = COMMIT;
  process.env.GITHUB_SHA = OTHER_COMMIT;
  expect((await version()).commit).toBe(COMMIT);
});

test("a short or malformed commit is not reported as the build's commit", async () => {
  process.env.VERCEL_GIT_COMMIT_SHA = "5c73b60";
  process.env.GITHUB_SHA = "not-a-commit";
  expect(await version()).toMatchObject({ commit: null, ref: null, environment: null });
});

test("the version says when the build ran, as an ISO instant", async () => {
  expect((await version()).builtAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
});
