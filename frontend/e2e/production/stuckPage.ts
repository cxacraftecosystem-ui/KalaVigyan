import type { CDPSession, Page } from "@playwright/test";

import { clip } from "./checks";

export const PAUSE_WAIT_MS = 5_000;
export const DEBUGGER_CALL_MS = 3_000;
const FRAMES_SHOWN = 6;
const SOURCE_SPAN = 120;

type CallFrame = {
  functionName: string;
  url: string;
  location: { scriptId: string; lineNumber: number; columnNumber?: number };
};

type Paused = { callFrames: CallFrame[] };

function delay(ms: number): Promise<null> {
  return new Promise((resolve) => setTimeout(() => resolve(null), ms));
}

export function within<T>(call: Promise<T>, ms: number): Promise<T | null> {
  return Promise.race([call.catch(() => null), delay(ms)]);
}

export async function answersScript(page: Page, withinMs: number): Promise<boolean> {
  return (await within(page.evaluate(() => true), withinMs)) === true;
}

export async function watchScript(page: Page): Promise<CDPSession> {
  const debuggerSession = await page.context().newCDPSession(page);
  await debuggerSession.send("Debugger.enable");
  return debuggerSession;
}

export async function stuckStack(debuggerSession: CDPSession): Promise<string[]> {
  const paused = new Promise<Paused>((resolve) => debuggerSession.once("Debugger.paused", (event) => resolve(event as Paused)));
  void debuggerSession.send("Debugger.pause").catch(() => undefined);
  const event = await Promise.race([paused, delay(PAUSE_WAIT_MS)]);
  if (event === null) return ["the debugger could not pause it, so the main thread is stuck outside script (style, layout or paint)"];
  const frames = await Promise.all(event.callFrames.slice(0, FRAMES_SHOWN).map((frame) => describeFrame(debuggerSession, frame)));
  await within(debuggerSession.send("Debugger.resume"), DEBUGGER_CALL_MS);
  return frames;
}

export async function stopScript(debuggerSession: CDPSession): Promise<boolean> {
  return (await within(debuggerSession.send("Runtime.terminateExecution").then(() => true), DEBUGGER_CALL_MS)) === true;
}

async function describeFrame(debuggerSession: CDPSession, frame: CallFrame): Promise<string> {
  const { scriptId, lineNumber, columnNumber = 0 } = frame.location;
  const where = `${frame.functionName || "(anonymous)"} at ${new URL(frame.url || "about:blank").pathname}:${lineNumber + 1}:${columnNumber + 1}`;
  const found = await within(debuggerSession.send("Debugger.getScriptSource", { scriptId }), DEBUGGER_CALL_MS);
  const source = (found as { scriptSource?: string } | null)?.scriptSource ?? "";
  const line = source.split("\n")[lineNumber] ?? "";
  const start = Math.max(0, columnNumber - SOURCE_SPAN / 2);
  return clip(`stuck in ${where}: ${line.slice(start, start + SOURCE_SPAN)}`, 400);
}
