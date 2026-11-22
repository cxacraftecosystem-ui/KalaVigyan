import { ENGLISH } from "@/lib/answerLanguages";
import type { VoiceAvailability } from "@/lib/voiceContract";

export const VOICE_BOARD_PATH = "/design/voice";
export const VOICE_BOARD_NOTICE_VERSION = "design-board-1";
export const VOICE_BOARD_SECONDS = 600;

export const VOICE_BOARD_AVAILABILITY: VoiceAvailability = {
  configured: true,
  transport: "RELAY",
  languages: [ENGLISH],
  noticeVersion: VOICE_BOARD_NOTICE_VERSION,
  consentRequired: true,
  remainingSeconds: VOICE_BOARD_SECONDS
};
