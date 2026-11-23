import { join } from "node:path";

import type { CDPSession, ConsoleMessage, Page, Request, Response } from "@playwright/test";

import { NetworkQuiet, captureScreen, readyForCapture, settle, sightProblems } from "./capture";
import { CITED_CONTENT, OVERFLOW_LIMIT, abortedRequest, clip, errorHeadline, gapCopyFindings, webkitLeavingNoise } from "./checks";
import type { Scheme } from "./matrix";
import { auditPage, sidewaysProblems } from "./pageAudit";
import { PageConsole } from "./pageConsole";
import type { ScreenOutcome, ScreensReport } from "./report";
import { SCREENSHOT_DIR, baseUrl, runFileName, runId, runStartedAt, writeReport } from "./run";
import { answersScript, stuckStack, watchScript } from "./stuckPage";

export type ScreenCheck = () => Promise<string[]>;

export type ExpectedResponse = { pathPrefix: string; status: number };

export type VisitOptions = { expectStatus?: number; expectedResponses?: readonly ExpectedResponse[]; expectedAlert?: string };

export type RunOptions = { scheme?: Scheme | null };

const STEP_LIMIT_MS = 180_000;
const ANSWER_WAIT_MS = 5_000;

export class ScreenRun {
  readonly screens: ScreenOutcome[] = [];
  private readonly page: Page;
  private readonly label: string;
  private readonly scheme: Scheme | null;
  private readonly origin: string;
  private readonly webkit: boolean;
  private readonly network: NetworkQuiet;
  private readonly consoleErrors: PageConsole;
  private signedIn = false;
  private expected: VisitOptions = {};
  private current: ScreenOutcome | null = null;
  private role: string | null = null;
  private everyScreenCheck: ScreenCheck | null = null;
  private debuggerSession: CDPSession | null = null;
  private stuckSince: string | null = null;

  constructor(page: Page, label: string, options: RunOptions = {}) {
    this.page = page;
    this.label = label;
    this.scheme = options.scheme ?? null;
    this.origin = new URL(baseUrl()).origin;
    this.webkit = page.context().browser()?.browserType().name() === "webkit";
    this.network = new NetworkQuiet(page);
    this.consoleErrors = new PageConsole(page, this.origin);
    page.on("console", (message) => this.onConsole(message));
    page.on("pageerror", (error) => this.onPageError(error));
    page.on("requestfailed", (request) => this.onRequestFailed(request));
    page.on("response", (response) => this.onResponse(response));
  }

  async watch(): Promise<void> {
    this.debuggerSession = await watchScript(this.page).catch(() => null);
  }

  markSignedIn(role: string | null): void {
    this.signedIn = true;
    this.role = role;
  }

  checkEveryScreen(check: ScreenCheck | null): void {
    this.everyScreenCheck = check;
  }

  flag(...problems: string[]): void {
    const current = this.current;
    if (!current) return;
    for (const problem of problems) if (!current.problems.includes(problem)) current.problems.push(problem);
  }

  note(...notes: string[]): void {
    this.current?.notes.push(...notes);
  }

  async visit(name: string, path: string, check?: ScreenCheck, options: VisitOptions = {}): Promise<void> {
    await this.screen(name, async () => {
      this.expected = options;
      const response = await this.page.goto(path, { waitUntil: "domcontentloaded" });
      const expected = options.expectStatus ?? 200;
      const status = response?.status() ?? 0;
      if (status !== expected) this.flag(`the page answered ${status}, expected ${expected}`);
      this.flag(...(await settle(this.page)));
      if (check) this.flag(...(await check()));
      await this.runEveryScreenCheck();
    });
  }

  async step(name: string, action: ScreenCheck): Promise<void> {
    await this.screen(name, async () => {
      this.flag(...(await action()));
      this.flag(...(await settle(this.page)));
      await this.runEveryScreenCheck();
    });
  }

  problemCount(): number {
    return this.screens.reduce((sum, screen) => sum + screen.problems.length, 0);
  }

  problemText(): string {
    return this.problemLines().join("\n");
  }

  problemLines(): string[] {
    return this.screens.flatMap((screen) => screen.problems.map((problem) => `${this.label} · ${screen.name}: ${problem}`));
  }

  write(): string {
    const report: ScreensReport = {
      kind: "screens",
      width: this.label,
      viewport: this.page.viewportSize(),
      baseUrl: baseUrl(),
      runId: runId(),
      startedAt: runStartedAt(),
      role: this.role,
      problemCount: this.problemCount(),
      screens: this.screens
    };
    return writeReport(runFileName({ subject: `${this.label} Screens`, what: "Report", ext: "json" }), report);
  }

  private async screen(name: string, body: () => Promise<void>): Promise<void> {
    const outcome: ScreenOutcome = { name, path: "", screenshot: null, durationMs: 0, problems: [], notes: [] };
    this.current = outcome;
    this.expected = {};
    this.screens.push(outcome);
    if (this.stuckSince) {
      this.flag(`skipped: the page stopped running script during ${this.stuckSince}`);
      return;
    }
    const started = Date.now();
    if (!(await this.bounded(body))) await this.diagnoseStuck(name);
    outcome.path = new URL(this.page.url()).pathname;
    if (!this.stuckSince) outcome.screenshot = await this.capture(name);
    outcome.durationMs = Date.now() - started;
  }

  private async bounded(body: () => Promise<void>): Promise<boolean> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const limit = new Promise<boolean>((resolve) => {
      timer = setTimeout(() => resolve(false), STEP_LIMIT_MS);
    });
    const work = (async () => {
      await body();
      this.flag(...(await readyForCapture(this.page, this.network)));
      await this.audit();
    })().then(
      () => true,
      (error: unknown) => {
        this.flag(`could not finish: ${errorHeadline(error)}`);
        return true;
      }
    );
    const finished = await Promise.race([work, limit]);
    clearTimeout(timer);
    return finished;
  }

  private async diagnoseStuck(name: string): Promise<void> {
    this.flag(`did not finish in ${STEP_LIMIT_MS / 1000} s`);
    if (await answersScript(this.page, ANSWER_WAIT_MS)) return;
    this.stuckSince = name;
    const stack = this.debuggerSession
      ? await stuckStack(this.debuggerSession).catch((error: unknown) => [`no stack: ${errorHeadline(error)}`])
      : ["no debugger session"];
    this.flag("the page stopped running script", ...stack);
  }

  private async runEveryScreenCheck(): Promise<void> {
    if (this.everyScreenCheck) this.flag(...(await this.everyScreenCheck()));
  }

  private async audit(): Promise<void> {
    const audit = await this.page.evaluate(auditPage, { citedSelector: CITED_CONTENT, limit: OVERFLOW_LIMIT });
    const expectedAlert = this.expected.expectedAlert;
    this.flag(...sidewaysProblems(audit));
    this.flag(...audit.textOverflow.map((finding) => `text overflow: ${finding}`));
    this.flag(...audit.alerts.filter((alert) => !(expectedAlert && alert.startsWith(expectedAlert))).map((alert) => `shows an error: ${clip(alert)}`));
    this.flag(...gapCopyFindings(audit.copy).map((finding) => `gap copy: "${finding}"`));
    this.flag(...(await sightProblems(this.page, this.scheme)));
  }

  private async capture(name: string): Promise<string | null> {
    const file = runFileName({
      subject: `${this.label} ${name}`,
      what: "Snapshot",
      ext: "png",
      sequence: String(this.screens.length).padStart(2, "0")
    });
    try {
      const captured = await captureScreen(this.page, join(SCREENSHOT_DIR, file));
      this.flag(...captured.problems);
      this.note(...captured.notes);
      return file;
    } catch (error) {
      this.flag(`no screenshot: ${errorHeadline(error)}`);
      return null;
    }
  }

  private sameOrigin(url: string): URL | null {
    const parsed = new URL(url);
    return parsed.origin === this.origin ? parsed : null;
  }

  private onPageError(error: Error): void {
    if (this.webkit && webkitLeavingNoise(`${error.name}: ${error.message}`, this.origin)) return;
    this.flag(`uncaught error: ${errorHeadline(error)}`);
  }

  private onConsole(message: ConsoleMessage): void {
    const problem = this.consoleErrors.problem(message);
    if (problem) this.flag(problem);
  }

  private onRequestFailed(request: Request): void {
    const url = this.sameOrigin(request.url());
    const failure = request.failure()?.errorText ?? "failed";
    if (!url || abortedRequest(failure)) return;
    this.flag(`${request.method()} ${url.pathname} failed: ${failure}`);
  }

  private expectedResponse(path: string, status: number, navigation: boolean): boolean {
    if (navigation && status === (this.expected.expectStatus ?? 200)) return true;
    return (this.expected.expectedResponses ?? []).some((allowed) => allowed.status === status && path.startsWith(allowed.pathPrefix));
  }

  private onResponse(response: Response): void {
    const url = this.sameOrigin(response.url());
    const status = response.status();
    if (!url || status < 400) return;
    if (!this.signedIn && status === 401 && url.pathname.startsWith("/api/")) return;
    if (this.expectedResponse(url.pathname, status, response.request().isNavigationRequest())) return;
    this.flag(`${response.request().method()} ${url.pathname} answered ${status}`);
  }
}
