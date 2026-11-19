import type { Fact } from "@/components/editorial/FactGrid";
import { formatDate, formatDateTime } from "@/lib/format";
import { hasOwnPassword } from "@/lib/passwordChange";
import type { User } from "@/lib/types";

const PROVIDER_LABEL: Record<string, string> = { GOOGLE: "Google", MICROSOFT: "Microsoft", YAHOO: "Yahoo", LOCAL: "Email and password" };

function shown(facts: Array<{ label: string; value: string | null | undefined }>): Fact[] {
  return facts.filter((fact): fact is Fact & { value: string } => typeof fact.value === "string" && fact.value.length > 0);
}

export function accountFacts(user: User): Fact[] {
  return shown([
    { label: "Email", value: user.email },
    { label: "Institution", value: user.affiliation },
    { label: "First signed in", value: user.firstLoginAt ? formatDate(user.firstLoginAt) : null },
    { label: "Last signed in", value: user.lastLoginAt ? formatDateTime(user.lastLoginAt) : null }
  ]);
}

export function signInFacts(user: User): Fact[] {
  const provider = PROVIDER_LABEL[(user.authProvider ?? "").toUpperCase()] ?? null;
  return shown([
    { label: "Signs in with", value: provider },
    { label: "Password", value: hasOwnPassword(user) ? (user.passwordSetAt ? `Set ${formatDate(user.passwordSetAt)}` : "Set") : "Not set" },
    { label: "Two-step verification", value: user.twoFactorEnabled ? (user.twoFactorEnabledAt ? `On since ${formatDate(user.twoFactorEnabledAt)}` : "On") : "Off" },
    { label: "Email confirmed", value: user.emailVerifiedAt ? formatDate(user.emailVerifiedAt) : null }
  ]);
}
