import { expect, test } from "@playwright/test";

import { parseShape } from "@/lib/shape";
import { VOICE_BOARD_AVAILABILITY, VOICE_BOARD_PATH } from "@/lib/voiceBoard";
import { voiceAvailabilityShape } from "@/lib/voiceContract";
import { voiceOffered } from "@/lib/voiceRules";

import { readRepo } from "./phaseBFixture";
import { FAKE_MICROPHONE_ARGS } from "./production/matrix";
import { HEARD_SENTENCE, RELAY_STARTED, RELAY_TURN, silentWav } from "./production/voiceDock";

test("the board offers a relay call in English with its notice to agree to", () => {
  expect(parseShape(voiceAvailabilityShape, VOICE_BOARD_AVAILABILITY)).toEqual(VOICE_BOARD_AVAILABILITY);
  expect(voiceOffered(VOICE_BOARD_AVAILABILITY, { agent: false, relayTypes: ["audio/webm;codecs=opus"] })).toBe(true);
  expect(VOICE_BOARD_AVAILABILITY.consentRequired && VOICE_BOARD_AVAILABILITY.noticeVersion).toBeTruthy();
  expect(readRepo("frontend", "app", "design", "voice", "page.tsx")).toContain("<VoiceDockBoard />");
  expect(VOICE_BOARD_PATH).toBe("/design/voice");
});

test("the check's reply plays half a second of silent 16-bit mono sound", () => {
  const wav = silentWav();
  expect(wav.subarray(0, 4).toString("ascii")).toBe("RIFF");
  expect(wav.subarray(8, 16).toString("ascii")).toBe("WAVEfmt ");
  expect([wav.readUInt16LE(22), wav.readUInt32LE(24), wav.readUInt16LE(34)]).toEqual([1, 8000, 16]);
  expect([wav.readUInt32LE(40), wav.length]).toEqual([8000, 8044]);
});

test("the check answers its turn with the relay golden of the same session", () => {
  expect(RELAY_TURN).toContain(HEARD_SENTENCE);
  expect(RELAY_TURN).toContain(`/api/voice/session/${RELAY_STARTED.voiceSessionId}/turns/`);
  expect(RELAY_TURN).toContain('"sessionEnded":false');
  expect(FAKE_MICROPHONE_ARGS).toEqual(["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]);
});
