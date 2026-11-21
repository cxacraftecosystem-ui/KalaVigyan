import type { ConsoleMessage, Page, Request, Response } from "@playwright/test";

import { abortedRequest, clip, errorHeadline } from "../production/checks";
import { isPreview, previewConsoleNoise } from "../production/preview";

import { checkRecord, keepRecord } from "./report";

export const ERROR_SCREEN = 'section[data-testid^="error-"]';
export const CONTROLS_CHECK = "controls";

export type ControlStep = { name: string; problems: string[]; notes: string[] };

export type DesignedAnswer = { pathPrefix: string; status: number };

export const DESIGNED_ANSWERS: readonly DesignedAnswer[] = [{ pathPrefix: "/api/shared-science/", status: 404 }];

const SAME_ORIGIN_RESOURCE = "Failed to load resource";
const UNKNOWN_WEBRTC_DIRECTIVE = "Unrecognized Content-Security-Policy directive 'webrtc'.";
const CHANGE_POLL_MS = 100;

export async function changedFrom(read: () => Promise<string>, before: string, timeoutMs: number): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const now = await read();
    if (now !== before || Date.now() >= deadline) return now;
    await new Promise((resolve) => setTimeout(resolve, CHANGE_POLL_MS));
  }
}

export async function reached(read: () => Promise<string>, wanted: string, timeoutMs: number): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const now = await read();
    if (now === wanted || Date.now() >= deadline) return now;
    await new Promise((resolve) => setTimeout(resolve, CHANGE_POLL_MS));
  }
}

export function designedAnswer(path: string, status: number): boolean {
  return DESIGNED_ANSWERS.some((answer) => answer.status === status && path.startsWith(answer.pathPrefix));
}

export class ControlWatch {
  readonly steps: ControlStep[] = [];
  private readonly preview: boolean;
  private signedIn = false;

  constructor(
    private readonly page: Page,
    private readonly target: string,
    private readonly origin: string
  ) {
    this.preview = isPreview(origin);
    page.on("console", (message) => this.onConsole(message));
    page.on("pageerror", (error) => this.flag(`uncaught error: ${errorHeadline(error)}`));
    page.on("requestfailed", (request) => this.onRequestFailed(request));
    page.on("response", (response) => this.onResponse(response));
  }

  markSignedIn(): void {
    this.signedIn = true;
  }

  async step(name: string, action: () => Promise<string[]>): Promise<void> {
    const step: ControlStep = { name, problems: [], notes: [] };
    this.steps.push(step);
    const problems = await action().catch((error: unknown) => [`could not finish: ${errorHeadline(error)}`]);
    this.flag(...problems);
    const screens = await this.page.locator(ERROR_SCREEN).evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-testid") ?? "")).catch(() => []);
    this.flag(...screens.map((screen) => `shows the error screen ${screen}`));
  }

  note(...notes: string[]): void {
    this.steps[this.steps.length - 1]?.notes.push(...notes);
  }

  flag(...problems: string[]): void {
    const step = this.steps[this.steps.length - 1];
    if (!step) return;
    for (const problem of problems) if (!step.problems.includes(problem)) step.problems.push(problem);
  }

  problems(): string[] {
    return this.steps.flatMap((step) => step.problems.map((problem) => `${step.name}: ${problem}`));
  }

  notes(): string[] {
    return this.steps.flatMap((step) => step.notes.map((note) => `${step.name}: ${note}`));
  }

  keep(): string[] {
    const problems = this.problems();
    keepRecord(checkRecord(CONTROLS_CHECK, this.target, problems, { notes: this.notes(), numbers: { steps: this.steps.length } }));
    return problems;
  }

  private sameOrigin(url: string): URL | null {
    const parsed = new URL(url);
    return parsed.origin === this.origin ? parsed : null;
  }

  private onConsole(message: ConsoleMessage): void {
    if (message.type() !== "error") return;
    const text = message.text();
    const from = message.location().url;
    if (text.startsWith(SAME_ORIGIN_RESOURCE) && from && this.sameOrigin(from)) return;
    if (text === UNKNOWN_WEBRTC_DIRECTIVE && from.startsWith("about:srcdoc")) return;
    if (this.preview && previewConsoleNoise(text, from)) return;
    this.flag(`console error: ${clip(text)}`);
  }

  private onRequestFailed(request: Request): void {
    const url = this.sameOrigin(request.url());
    const failure = request.failure()?.errorText ?? "failed";
    if (!url || abortedRequest(failure)) return;
    this.flag(`${request.method()} ${url.pathname} failed: ${failure}`);
  }

  private onResponse(response: Response): void {
    const url = this.sameOrigin(response.url());
    const status = response.status();
    if (!url || status < 400) return;
    if (!this.signedIn && status === 401 && url.pathname.startsWith("/api/")) return;
    if (designedAnswer(url.pathname, status)) return;
    this.flag(`${response.request().method()} ${url.pathname} answered ${status}`);
  }
}
