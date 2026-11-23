import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { Page } from "@playwright/test";

import { VOICE_BOARD_NOTICE_VERSION } from "../../lib/voiceBoard";
import { FRONTEND } from "../moduleGraph";

export type SentTurn = { contentType: string; bytes: number; body: Buffer };

const SHARED = join(FRONTEND, "..", "shared");
const SPEECH_RATE = 8_000;
const SPEECH_SECONDS = 0.5;

function golden(name: string): string {
  return readFileSync(join(SHARED, name), "utf8");
}

export type RelayStarted = { voiceSessionId: string; maxTurnSeconds: number; maxAudioBytes: number; audioBitsPerSecond: number };

export const RELAY_STARTED = JSON.parse(golden("voice.session-relay.golden.json")) as RelayStarted;
export const RELAY_TURN = golden("voice.turn.golden.sse");
export const HEARD_SENTENCE = "Alum is used as a mordant to fasten the colours.";
const SPEECH_PATH = /\/api\/voice\/session\/[^/]+\/turns\/[^/]+\/speech$/;

export function silentWav(seconds = SPEECH_SECONDS, rate = SPEECH_RATE): Buffer {
  const samples = Math.round(seconds * rate);
  const header = Buffer.alloc(44);
  header.write("RIFF", 0, "ascii");
  header.writeUInt32LE(36 + samples * 2, 4);
  header.write("WAVEfmt ", 8, "ascii");
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(rate, 24);
  header.writeUInt32LE(rate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36, "ascii");
  header.writeUInt32LE(samples * 2, 40);
  return Buffer.concat([header, Buffer.alloc(samples * 2)]);
}

export async function routeRelayCall(page: Page, sent: SentTurn[]): Promise<void> {
  const session = `**/api/voice/session/${RELAY_STARTED.voiceSessionId}`;
  const notice = { version: VOICE_BOARD_NOTICE_VERSION, title: "Voice calls", body: "A call records only while you talk.", publishedAt: null };
  await page.route("**/api/voice/notice", (route) => route.fulfill({ json: notice }));
  await page.route("**/api/auth/consent", (route) => route.fulfill({ json: { recorded: true } }));
  await page.route("**/api/voice/session", (route) => route.fulfill({ status: 201, json: RELAY_STARTED }));
  await page.route(`${session}/turns`, async (route) => {
    const request = route.request();
    const body = request.postDataBuffer() ?? Buffer.alloc(0);
    sent.push({ contentType: request.headers()["content-type"] ?? "", bytes: body.length, body });
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: RELAY_TURN });
  });
  await page.route(SPEECH_PATH, (route) => route.fulfill({ status: 200, contentType: "audio/wav", body: silentWav() }));
  await page.route(`${session}/end`, (route) => route.fulfill({ json: JSON.parse(golden("voice.session-ended.golden.json")) }));
  await page.route(`${session}/transcript`, (route) => route.fulfill({ json: JSON.parse(golden("voice.transcript.golden.json")) }));
}
