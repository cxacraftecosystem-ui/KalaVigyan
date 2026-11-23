import { expect, test } from "@playwright/test";

import { formFile, fullMinuteCeiling } from "./voiceRate";

const AUDIO = Buffer.from([1, 2, 3, 13, 10, 4]);

function form(boundary: string): Buffer {
  return Buffer.concat([
    Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nen\r\n`),
    Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="audio"; filename="turn.webm"\r\nContent-Type: audio/webm\r\n\r\n`),
    AUDIO,
    Buffer.from(`\r\n--${boundary}--\r\n`)
  ]);
}

test("the recorded file is read out of the multipart upload byte for byte", () => {
  const file = formFile(form("XyZ"), "multipart/form-data; boundary=XyZ", "audio");
  expect(file.type).toBe("audio/webm");
  expect([...file.data]).toEqual([1, 2, 3, 13, 10, 4]);
  expect([...formFile(form("q-1"), 'multipart/form-data; boundary="q-1"', "audio").data]).toEqual([1, 2, 3, 13, 10, 4]);
  expect(() => formFile(form("XyZ"), "multipart/form-data; boundary=XyZ", "picture")).toThrow("no picture file");
  expect(() => formFile(form("XyZ"), "multipart/form-data", "audio")).toThrow("no multipart boundary");
});

test("a full minute fits under the send point at no more than 36,000 bit/s for the relay's 300,000 bytes", () => {
  expect(fullMinuteCeiling(300_000, 60)).toBe(36_000);
  expect(fullMinuteCeiling(1_000, 1)).toBe(7_200);
});
