
import { expect, test } from "@playwright/test";
import { createElement, Suspense, type ComponentType, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { prerender } from "react-dom/static";

import { BLOCK_FAILED, BlockBoundary, retryableLazy } from "@/components/answer/lazyBlock";

async function prerendered(Block: ComponentType<object>): Promise<{ html: string; errors: unknown[] }> {
  const errors: unknown[] = [];
  const { prelude } = await prerender(createElement(Suspense, { fallback: "waiting" }, createElement(Block)), { onError: (cause) => void errors.push(cause) });
  return { html: await new Response(prelude).text(), errors };
}

test("a block whose chunk fails to load raises the failure, and Try again draws it from a fresh import", async () => {
  let loads = 0;
  const Drawn = () => createElement("p", null, "drawn");
  const loader = retryableLazy<object>(() => {
    loads += 1;
    return loads === 1 ? Promise.reject(new Error("the chunk did not arrive")) : Promise.resolve(Drawn);
  });
  const failed = loader.current();
  const first = await prerendered(failed);
  expect(first.errors.map((cause) => (cause as Error).message)).toEqual(["the chunk did not arrive"]);
  expect(first.html).not.toContain("drawn");
  const again = loader.retry(failed);
  expect(again).not.toBe(failed);
  expect(loader.retry(failed)).toBe(again);
  const second = await prerendered(again);
  expect(second.errors).toEqual([]);
  expect(second.html).toContain("<p>drawn</p>");
  expect(loads).toBe(2);
});

test("the block's boundary draws the failure in words with one Try again", () => {
  expect(BlockBoundary.getDerivedStateFromError()).toEqual({ failed: true });
  const retried: string[] = [];
  const boundary = new BlockBoundary({ children: "the map", onRetry: () => retried.push("again") });
  expect(renderToStaticMarkup(createElement("div", null, boundary.render()))).toBe("<div>the map</div>");
  boundary.state = { failed: true };
  const html = renderToStaticMarkup(boundary.render() as ReactElement);
  expect(html).toContain('role="alert"');
  expect(html).toContain(BLOCK_FAILED);
  expect(html.match(/<button/g)).toHaveLength(1);
  expect(html).toContain("Try again");
});
