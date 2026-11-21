import { expect, test } from "@playwright/test";

import { modelsForTask, type RouteProvider, type TaskRoute } from "@/lib/routing";

const PROVIDERS: RouteProvider[] = [
  {
    id: "GEMINI",
    name: "Google Gemini",
    keyName: "GEMINI_API_KEY",
    keyState: "PASSING",
    publicTextOnly: false,
    models: [{ id: "gemini-embedding-2", label: "Gemini Embedding 2", tasks: ["EMBED"] }]
  },
  {
    id: "VOYAGE",
    name: "Voyage AI",
    keyName: "VOYAGE_API_KEY",
    keyState: "UNTESTED",
    publicTextOnly: false,
    models: [{ id: "rerank-3", label: "Voyage Rerank 3", tasks: ["RERANK"] }]
  }
];

function task(name: string): TaskRoute {
  return { task: name, label: name, publicText: false, routes: [], effectiveChain: [], normalisedNote: null };
}

test("the rerank task offers Voyage Rerank 3 and no other task does", () => {
  const rerank = modelsForTask(PROVIDERS, task("RERANK")).map(({ provider, model }) => `${provider.id}:${model.id}`);
  const embed = modelsForTask(PROVIDERS, task("EMBED")).map(({ provider, model }) => `${provider.id}:${model.id}`);
  expect(rerank).toEqual(["VOYAGE:rerank-3"]);
  expect(embed).toEqual(["GEMINI:gemini-embedding-2"]);
});
