import type { Page } from "@playwright/test";

import { fullAt } from "../lib/voiceDevice";

export type FormFile = { type: string; data: Buffer };
export type RecordedRate = { type: string; bytes: number; seconds: number; bitsPerSecond: number };

const PART_BREAK = Buffer.from("\r\n\r\n");

function boundaryOf(contentType: string): Buffer {
  const found = /boundary=(?:"([^"]+)"|([^;\s]+))/i.exec(contentType);
  if (!found) throw new Error(`no multipart boundary in ${contentType}`);
  return Buffer.from(`--${found[1] ?? found[2]}`);
}

export function formFile(body: Buffer, contentType: string, field: string): FormFile {
  const marker = boundaryOf(contentType);
  let at = body.indexOf(marker);
  while (at >= 0) {
    const next = body.indexOf(marker, at + marker.length);
    if (next < 0) break;
    const part = body.subarray(at + marker.length + 2, next - 2);
    const split = part.indexOf(PART_BREAK);
    const head = part.subarray(0, split).toString("utf8");
    if (head.includes(`name="${field}"`)) {
      const type = /content-type:\s*([^\r\n;]+)/i.exec(head)?.[1]?.trim() ?? "";
      return { type, data: part.subarray(split + PART_BREAK.length) };
    }
    at = next;
  }
  throw new Error(`the form has no ${field} file`);
}

export async function decodedSeconds(page: Page, audio: Buffer): Promise<number> {
  return page.evaluate(async (base64) => {
    const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
    const decoded = await new OfflineAudioContext(1, 1, 48_000).decodeAudioData(bytes.buffer);
    return decoded.duration;
  }, audio.toString("base64"));
}

export async function recordedRate(page: Page, file: FormFile): Promise<RecordedRate> {
  const seconds = await decodedSeconds(page, file.data);
  return { type: file.type, bytes: file.data.length, seconds, bitsPerSecond: Math.round((file.data.length * 8) / seconds) };
}

export function fullMinuteCeiling(maxAudioBytes: number, maxTurnSeconds: number): number {
  return Math.floor((fullAt(maxAudioBytes) * 8) / maxTurnSeconds);
}
