import { disableTwoFactor, enableTwoFactor, makeNewRecoveryCodes } from "@/lib/twoFactor";

export type TwoStepCodePhase = "setup" | "regenerate" | "disable";

export type TwoStepAnswer = { kind: "codes"; codes: string[] } | { kind: "off" };

export async function answerTwoStepCode(phase: TwoStepCodePhase, code: string): Promise<TwoStepAnswer> {
  if (phase === "disable") {
    await disableTwoFactor(code);
    return { kind: "off" };
  }
  return { kind: "codes", codes: phase === "setup" ? await enableTwoFactor(code) : await makeNewRecoveryCodes(code) };
}

export function readsAccountNow(answer: TwoStepAnswer): boolean {
  return answer.kind === "off";
}
