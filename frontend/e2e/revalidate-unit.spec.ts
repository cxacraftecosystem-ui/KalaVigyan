import { expect, test } from "@playwright/test";

import {
  handleRevalidate,
  parsedRevalidation,
  REVALIDATE_ROUTE,
  REVALIDATE_SECRET_HEADER,
  sameSecret,
  TARGETS_MAX
} from "@/lib/server/revalidation";

const SECRET = "revalidate-test-secret";
const BACKEND_ASKS = {
  paths: ["/crafts/Ajrakh", "/crafts/Ajrakh/monograph", "/categories/textiles", "/categories/textiles/monograph"],
  tags: ["craft-page:Ajrakh", "monograph-document:craft:Ajrakh", "monograph-document:category:textiles"]
};

type Refreshed = { paths: string[]; tags: string[] };

function asked(body: unknown, secret: string | null = SECRET): Request {
  const headers = new Headers({ "content-type": "application/json" });
  if (secret !== null) headers.set(REVALIDATE_SECRET_HEADER, secret);
  return new Request(`https://kalavigyan.example${REVALIDATE_ROUTE}`, { method: "POST", headers, body: JSON.stringify(body) });
}

async function handled(request: Request, env: Record<string, string | undefined> = { WEB_REVALIDATE_SECRET: SECRET }) {
  const refreshed: Refreshed = { paths: [], tags: [] };
  const response = await handleRevalidate(request, {
    env,
    refreshPath: (path) => refreshed.paths.push(path),
    refreshTag: (tag) => refreshed.tags.push(tag)
  });
  return { status: response.status, body: await response.json(), refreshed };
}

test("the pages and tags the backend names are refreshed once the shared secret matches", async () => {
  const { status, body, refreshed } = await handled(asked(BACKEND_ASKS));
  expect(status).toBe(200);
  expect(refreshed).toEqual(BACKEND_ASKS);
  expect(body).toEqual({ revalidated: BACKEND_ASKS });
});

test("a missing or wrong secret refreshes nothing, and an unset secret refuses every request", async () => {
  for (const secret of [null, "", "revalidate-test-secreT", `${SECRET}-2`]) {
    const { status, refreshed } = await handled(asked(BACKEND_ASKS, secret));
    expect([status, refreshed.paths.length + refreshed.tags.length]).toEqual([401, 0]);
  }
  const unset = await handled(asked(BACKEND_ASKS), {});
  expect([unset.status, unset.refreshed.paths.length]).toEqual([503, 0]);
});

test("only craft and category pages and their document tags may be refreshed", async () => {
  for (const body of [
    { paths: ["/admin/review"], tags: [] },
    { paths: ["/crafts/Ajrakh/../admin"], tags: [] },
    { paths: [], tags: ["static-pages"] },
    { paths: [], tags: [] },
    { paths: "/crafts/Ajrakh", tags: [] },
    { paths: Array.from({ length: TARGETS_MAX + 1 }, (_, index) => `/crafts/Craft-${index}`), tags: [] }
  ]) {
    expect(parsedRevalidation(body)).toBeNull();
  }
  const { status, refreshed } = await handled(asked({ paths: ["/admin/review"], tags: [] }));
  expect([status, refreshed.paths]).toEqual([422, []]);
  expect(parsedRevalidation({ paths: ["/crafts/A", "/crafts/A"], tags: [] })).toEqual({ paths: ["/crafts/A"], tags: [] });
});

test("the secret comparison needs the exact secret whatever its length", () => {
  expect(sameSecret(SECRET, SECRET)).toBe(true);
  expect(sameSecret("short", SECRET)).toBe(false);
  expect(sameSecret(SECRET, "")).toBe(false);
  expect(sameSecret(null, SECRET)).toBe(false);
});
