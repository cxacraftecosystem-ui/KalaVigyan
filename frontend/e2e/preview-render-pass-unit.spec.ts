import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { RENDER_PASS_HEADER, upstreamHeaders, upstreamUrl } from "@/lib/server/apiProxy";
import { renderPassFetch } from "@/lib/server/serverFetch";

import { drawnApiPath, renderPassOf } from "../app/(reading)/preview/[token]/previewDocument";

const PASS = `${"a".repeat(32)}.1795000000.${"b".repeat(64)}`;
const TOKEN = `${"c".repeat(32)}.1795000000.${"d".repeat(64)}`;
const ENV = { API_ORIGIN: "https://api.example.test", NODE_ENV: "production", WEB_PROXY_SECRET: "proxy" };
const RENDER_CONTRACT = join(__dirname, "..", "..", "backend", "app", "research", "page_render.py");
const PREVIEW_ROUTES = join(__dirname, "..", "..", "backend", "app", "api", "routes", "page_proposals.py");
const FIELD_ROUTES = join(__dirname, "..", "..", "backend", "app", "api", "routes", "field_voices.py");
const PICTURE = "0e000000-0000-4000-8000-000000000001";
const FIELD_PHOTO = "1346266a-fb2a-57ed-90be-33d2299119d4";

type Call = { url: string; init: RequestInit };

function recorder(): { calls: Call[]; fetcher: typeof fetch } {
  const calls: Call[] = [];
  const fetcher = (async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init: init ?? {} });
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
  }) as typeof fetch;
  return { calls, fetcher };
}

test("the render pass header and the routes it opens are the ones the API serves", () => {
  const contract = readFileSync(RENDER_CONTRACT, "utf8");
  const found = /^RENDER_PASS_HEADER = "([^"]+)"$/m.exec(contract);
  expect(found?.[1]).toBe(RENDER_PASS_HEADER);
  const routes = readFileSync(PREVIEW_ROUTES, "utf8");
  expect(routes).toContain('router = APIRouter(prefix="/knowledge/pages"');
  expect(routes).toContain('@router.get("/previews/{token}/drawn")');
  expect(routes).toContain('@router.get("/drawn-pictures/{contribution_id}")');
  expect(routes).toContain('@router.get("/drawn-field-photos/{image_id}")');
  expect(readFileSync(FIELD_ROUTES, "utf8")).toContain('@router.get("/field-voices/images/{image_id}")');
});

test("a preview request carries a pass only when the header holds one of the preview link's shape", () => {
  expect(renderPassOf(new Headers({ [RENDER_PASS_HEADER]: PASS }))).toBe(PASS);
  expect(renderPassOf(new Headers({ [RENDER_PASS_HEADER]: "not a pass" }))).toBeNull();
  expect(renderPassOf(new Headers())).toBeNull();
});

test("the preview page reads its document with the pass in place of a session", async () => {
  const sent = recorder();
  const result = await renderPassFetch(drawnApiPath(TOKEN), { parse: (body) => body, pass: PASS, deps: { fetcher: sent.fetcher, env: ENV } });
  expect(result).toEqual({ ok: true, body: { ok: true } });
  const [call] = sent.calls;
  expect(call.url).toBe(`https://api.example.test/api/knowledge/pages/previews/${TOKEN}/drawn`);
  const headers = new Headers(call.init.headers);
  expect(headers.get(RENDER_PASS_HEADER)).toBe(PASS);
  expect(headers.get("authorization")).toBeNull();
  expect(headers.get("x-web-proxy-secret")).toBe("proxy");
  expect(call.init.cache).toBe("no-store");
});

test("a preview's picture fetched by the renderer goes to the pass's own route with its pass and without cookies", () => {
  const request = new Request(`https://kalavigyan.example/api/knowledge/pages/pictures/${PICTURE}?theme=light`, {
    headers: { [RENDER_PASS_HEADER]: PASS, cookie: "kv_other=1", accept: "image/avif,image/webp" }
  });
  expect(upstreamUrl(request, "https://api.example.test")).toBe(`https://api.example.test/api/knowledge/pages/drawn-pictures/${PICTURE}?theme=light`);
  const reader = new Request(`https://kalavigyan.example/api/knowledge/pages/pictures/${PICTURE}`);
  expect(upstreamUrl(reader, "https://api.example.test")).toBe(`https://api.example.test/api/knowledge/pages/pictures/${PICTURE}`);
  const headers = upstreamHeaders(request, null, {});
  expect(headers.get(RENDER_PASS_HEADER)).toBe(PASS);
  expect(headers.get("cookie")).toBeNull();
  expect(headers.get("authorization")).toBeNull();
  expect(headers.get("accept")).toBe("image/avif,image/webp");
});

test("a field photograph the renderer fetches is served by the pass's own route from the site, and a reader's still goes to the public route", () => {
  const drawn = new Request(`https://kalavigyan.example/api/field-voices/images/${FIELD_PHOTO}`, { headers: { [RENDER_PASS_HEADER]: PASS, accept: "image/avif,image/webp" } });
  expect(upstreamUrl(drawn, "https://api.example.test")).toBe(`https://api.example.test/api/knowledge/pages/drawn-field-photos/${FIELD_PHOTO}`);
  expect(upstreamHeaders(drawn, null, {}).get(RENDER_PASS_HEADER)).toBe(PASS);
  const reader = new Request(`https://kalavigyan.example/api/field-voices/images/${FIELD_PHOTO}`);
  expect(upstreamUrl(reader, "https://api.example.test")).toBe(`https://api.example.test/api/field-voices/images/${FIELD_PHOTO}`);
  const other = new Request("https://kalavigyan.example/api/field-voices/recordings/r1", { headers: { [RENDER_PASS_HEADER]: PASS } });
  expect(upstreamUrl(other, "https://api.example.test")).toBe("https://api.example.test/api/field-voices/recordings/r1");
});
