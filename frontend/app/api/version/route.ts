import { NextResponse } from "next/server";

export const dynamic = "force-static";

const COMMIT = /^[0-9a-f]{40}$/;
const BUILT_AT = new Date().toISOString();

function buildCommit(env: NodeJS.ProcessEnv): string | null {
  for (const value of [env.VERCEL_GIT_COMMIT_SHA, env.GITHUB_SHA]) {
    const commit = (value ?? "").trim().toLowerCase();
    if (COMMIT.test(commit)) return commit;
  }
  return null;
}

function named(value: string | undefined): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : null;
}

export function GET() {
  return NextResponse.json({
    commit: buildCommit(process.env),
    ref: named(process.env.VERCEL_GIT_COMMIT_REF),
    environment: named(process.env.VERCEL_ENV),
    builtAt: BUILT_AT
  });
}
