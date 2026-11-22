import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { HEAVY_STEPS, SIGN_IN_BUDGET_MS, heavyStep, signInProblems, untilHeavy } from "./signInProbe";

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    }
  });
}

const PLANNING = 'event: status\ndata: {"step":"PLANNING","message":"Planning the research on Kutch Ajrakh"}\n\n';
const RESEARCHING = 'event: status\ndata: {"step":"RESEARCHING","message":"Searching 6 live queries"}\n\n';

test("a sign-in over ten seconds beside an Expert answer is a problem, and one under is not", () => {
  expect(SIGN_IN_BUDGET_MS).toBe(10_000);
  expect(signInProblems([850, 9_999, 10_000])).toEqual([]);
  expect(signInProblems([850, 61_200])).toEqual(["sign-in took 61.2 s while an Expert answer ran, over its 10 s budget"]);
});

test("the probe signs in again once the answer's research has begun", () => {
  expect([...HEAVY_STEPS]).toEqual(["RESEARCHING", "READING", "COMPOSING", "WRITING_BACK"]);
  expect(heavyStep(PLANNING.trim())).toBeNull();
  expect(heavyStep(RESEARCHING.trim())).toBe("RESEARCHING");
  expect(heavyStep('event: error\ndata: {"message":"Research failed just now. Try again."}')).toBe("error");
  expect(heavyStep(": keep-alive")).toBeNull();
});

test("waiting for the research reads the stream across chunks and reports an answer that ends early", async () => {
  expect(await untilHeavy(streamOf(PLANNING, RESEARCHING.slice(0, 20), RESEARCHING.slice(20)))).toBeNull();
  expect(await untilHeavy(streamOf(PLANNING))).toBe("the Expert answer ended before its research began");
  expect(await untilHeavy(streamOf(PLANNING, 'event: done\ndata: {"answerId":null}\n\n'))).toBe("the Expert answer sent done before its research began");
});

test("the release check runs the probe only after a backend deploy", () => {
  const workflow = readFileSync(join(__dirname, "..", "..", "..", ".github", "workflows", "post-deploy.yml"), "utf8");
  expect(workflow).toContain("E2E_SIGN_IN_PROBE: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.name == 'Deploy backend' && '1' || '' }}");
});
