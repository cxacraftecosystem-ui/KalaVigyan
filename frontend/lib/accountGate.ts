import { mustChangePassword } from "@/lib/signIn";
import type { User } from "@/lib/types";

export type AccountStep = "first-password" | "two-step" | "first-entry" | "guardian";

export function accountStepFor(user: User | null): AccountStep | null {
  if (!user) return null;
  if (mustChangePassword(user)) return "first-password";
  if (user.twoFactorRequired && !user.twoFactorEnabled) return "two-step";
  if (user.profileRequired) return "first-entry";
  if (user.guardianConsentRequired) return "guardian";
  return null;
}
