import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { VoiceSettingsForm } from "@/components/admin/VoiceSettingsForm";
import { parseShape, ShapeError } from "@/lib/shape";
import { LIVE_CALLS_MAX, VOICE_ID, voiceSettingProblems, voiceSettingsViewShape, type VoiceSettingsView } from "@/lib/voiceSettingsContract";

import { readRepo } from "./phaseBFixture";

const DEFAULTS = { transport: "RELAY", maxLiveSessions: 5, voiceId: "JBFqnCBsd6RMkjVDRZzb" } as const;
const VIEW: VoiceSettingsView = { transport: "AGENT", maxLiveSessions: 12, voiceId: "Xb7hH8MSUJpSbSDYk0k2", defaults: DEFAULTS };

test("the voice settings view is read in the server's shape and refuses an unknown transport", () => {
  expect(parseShape(voiceSettingsViewShape, VIEW)).toEqual(VIEW);
  expect(() => parseShape(voiceSettingsViewShape, { ...VIEW, transport: "PHONE" })).toThrow(ShapeError);
  expect(() => parseShape(voiceSettingsViewShape, { ...VIEW, maxLiveSessions: 2.5 })).toThrow(ShapeError);
});

test("a draft is checked as the server checks it", () => {
  const draft = { transport: "RELAY", maxLiveSessions: "12", voiceId: "JBFqnCBsd6RMkjVDRZzb" } as const;
  expect(voiceSettingProblems(draft)).toEqual({});
  for (const calls of ["", "-1", "2.5", "101", "many"]) expect(Object.keys(voiceSettingProblems({ ...draft, maxLiveSessions: calls }))).toEqual(["maxLiveSessions"]);
  for (const voice of ["", "a voice", "voice-1"]) expect(Object.keys(voiceSettingProblems({ ...draft, voiceId: voice }))).toEqual(["voiceId"]);
  const admin = readRepo("backend", "app", "schemas", "admin.py");
  expect(admin).toContain(`VOICE_ID_PATTERN = r"${VOICE_ID.source}"`);
  expect(admin).toContain(`MAX_LIVE_SESSIONS_CEILING = ${LIVE_CALLS_MAX}`);
});

test("the form shows each setting with its default and saves with one primary button", () => {
  const html = renderToStaticMarkup(createElement(VoiceSettingsForm, { view: VIEW, busy: false, onSave: () => undefined }));
  expect(html).toContain("How a call is carried");
  expect(html).toContain("Default: relay.");
  expect(html).toContain("0 to 100. Default: 5.");
  expect(html).toContain('value="Xb7hH8MSUJpSbSDYk0k2"');
  expect(html).toContain('aria-pressed="true">ElevenLabs agent</button>');
  expect((html.match(/data-variant="primary"/g) ?? []).length).toBe(1);
});

test("the settings hub draws the voice block for a Master Admin", () => {
  expect(readRepo("frontend", "app", "(protected)", "admin", "page.tsx")).toContain("<VoiceSettingsCard />");
  expect(readRepo("frontend", "components", "admin", "VoiceSettingsCard.tsx")).toContain("canManageRouting(user)");
});
