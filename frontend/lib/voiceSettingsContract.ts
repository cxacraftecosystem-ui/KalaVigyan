import { apiFetch } from "@/lib/api";
import { integer, object, oneOf, parseShape, text, type Shape } from "@/lib/shape";

export const VOICE_SETTINGS_PATH = "/settings/voice";
export const VOICE_TRANSPORTS = ["RELAY", "AGENT"] as const;
export const LIVE_CALLS_MAX = 100;
export const VOICE_ID = /^[A-Za-z0-9]{1,64}$/;

export type VoiceTransport = (typeof VOICE_TRANSPORTS)[number];
export type VoiceSettings = { transport: VoiceTransport; maxLiveSessions: number; voiceId: string };
export type VoiceSettingsView = VoiceSettings & { defaults: VoiceSettings };
export type VoiceSettingsDraft = { transport: VoiceTransport; maxLiveSessions: string; voiceId: string };
export type VoiceSettingsProblems = Partial<Record<"maxLiveSessions" | "voiceId", string>>;

export const TRANSPORT_LABELS: Record<VoiceTransport, string> = { RELAY: "Relay", AGENT: "ElevenLabs agent" };

const settingsFields = { transport: oneOf(VOICE_TRANSPORTS), maxLiveSessions: integer, voiceId: text };
const voiceSettingsShape: Shape<VoiceSettings> = object<VoiceSettings>(settingsFields);

export const voiceSettingsViewShape: Shape<VoiceSettingsView> = object<VoiceSettingsView>({ ...settingsFields, defaults: voiceSettingsShape });

export function voiceDraft(settings: VoiceSettings): VoiceSettingsDraft {
  return { transport: settings.transport, maxLiveSessions: String(settings.maxLiveSessions), voiceId: settings.voiceId };
}

export function voiceSettingProblems(draft: VoiceSettingsDraft): VoiceSettingsProblems {
  const problems: VoiceSettingsProblems = {};
  const calls = Number(draft.maxLiveSessions.trim());
  if (draft.maxLiveSessions.trim() === "" || !Number.isInteger(calls) || calls < 0 || calls > LIVE_CALLS_MAX) {
    problems.maxLiveSessions = `Enter a whole number from 0 to ${LIVE_CALLS_MAX}.`;
  }
  if (!VOICE_ID.test(draft.voiceId.trim())) problems.voiceId = "Enter the voice id as ElevenLabs shows it: letters and digits only.";
  return problems;
}

export function draftSettings(draft: VoiceSettingsDraft): VoiceSettings {
  return { transport: draft.transport, maxLiveSessions: Number(draft.maxLiveSessions.trim()), voiceId: draft.voiceId.trim() };
}

export async function fetchVoiceSettings(): Promise<VoiceSettingsView> {
  return parseShape(voiceSettingsViewShape, await apiFetch<unknown>(VOICE_SETTINGS_PATH));
}

export async function saveVoiceSettings(settings: VoiceSettings): Promise<VoiceSettingsView> {
  const body = await apiFetch<unknown>(VOICE_SETTINGS_PATH, { method: "PUT", body: JSON.stringify(settings) });
  return parseShape(voiceSettingsViewShape, body);
}
