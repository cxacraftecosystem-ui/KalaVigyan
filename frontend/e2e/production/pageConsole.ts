import type { ConsoleMessage, Frame, Page, Request } from "@playwright/test";

import { clip, webkitLeavingNoise } from "./checks";
import { isPreview, previewConsoleNoise } from "./preview";

const SAME_ORIGIN_RESOURCE = "Failed to load resource";
const UNKNOWN_WEBRTC_DIRECTIVE = "Unrecognized Content-Security-Policy directive 'webrtc'.";
const INHERITS_ITS_PARENT = /^(about:|data:)/;

export function requestFrame(request: Request): Frame | null {
  try {
    return request.frame();
  } catch {
    return null;
  }
}

export class PageConsole {
  private readonly loadedBy = new Map<string, Set<Frame>>();
  private readonly preview: boolean;
  private readonly webkit: boolean;

  constructor(
    private readonly page: Page,
    private readonly origin: string
  ) {
    this.preview = isPreview(origin);
    this.webkit = page.context().browser()?.browserType().name() === "webkit";
    page.on("request", (request) => this.onRequest(request));
  }

  problem(message: ConsoleMessage): string | null {
    if (message.type() !== "error") return null;
    const text = message.text();
    const from = message.location().url;
    if (!this.fromOurFrames(from)) return null;
    if (text.startsWith(SAME_ORIGIN_RESOURCE) && this.sameOrigin(from)) return null;
    if (text === UNKNOWN_WEBRTC_DIRECTIVE && from.startsWith("about:srcdoc")) return null;
    if (this.webkit && webkitLeavingNoise(text, this.origin)) return null;
    if (this.preview && previewConsoleNoise(text, from)) return null;
    return `console error: ${clip(text)}`;
  }

  fromOurFrames(url: string): boolean {
    if (!url) return true;
    const frames = this.loadedBy.get(url) ?? new Set(this.page.frames().filter((frame) => frame.url() === url));
    return frames.size === 0 || [...frames].some((frame) => this.ours(frame));
  }

  private ours(frame: Frame): boolean {
    if (frame === this.page.mainFrame()) return true;
    if (INHERITS_ITS_PARENT.test(frame.url())) {
      const parent = frame.parentFrame();
      return parent === null || this.ours(parent);
    }
    return this.sameOrigin(frame.url());
  }

  private sameOrigin(url: string): boolean {
    return url === this.origin || url.startsWith(`${this.origin}/`);
  }

  private onRequest(request: Request): void {
    const frame = requestFrame(request);
    if (frame === null) return;
    const url = request.url();
    this.loadedBy.set(url, new Set([...(this.loadedBy.get(url) ?? []), frame]));
  }
}
