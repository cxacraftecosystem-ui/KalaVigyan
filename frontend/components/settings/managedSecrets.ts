import type { StatusTone } from "@/components/records/statusTone";
import { apiFetch } from "@/lib/api";

export type SecretSource = "database" | "environment" | "unset";
export type SecretStatus = "UNKNOWN" | "OK" | "FAILED";

export type ManagedSecret = {
  key: string;
  label: string;
  description: string;
  configured: boolean;
  source: SecretSource;
  overrideUnreadable?: boolean;
  hint: string | null;
  lastStatus: SecretStatus;
  lastCheckedAt: string | null;
  lastError: string | null;
  updatedBy: string | null;
  updatedAt: string | null;
};

export type SecretMeta = { label: string; tone: StatusTone; help: string };

export const SOURCE_META: Record<SecretSource, SecretMeta> = {
  database: { label: "Saved here", tone: "info", help: "This value overrides the default." },
  environment: { label: "Default", tone: "neutral", help: "The default value is in use. Saving here overrides it." },
  unset: { label: "Not set", tone: "warning", help: "The features that need it are off." }
};

export const STATUS_META: Record<SecretStatus, { label: string; tone: StatusTone }> = {
  OK: { label: "Working", tone: "success" },
  FAILED: { label: "Test failed", tone: "error" },
  UNKNOWN: { label: "Not tested", tone: "neutral" }
};

export function hasStoredOverride(secret: Pick<ManagedSecret, "source" | "overrideUnreadable">): boolean {
  return secret.source === "database" || secret.overrideUnreadable === true;
}

export function maskedValue(secret: Pick<ManagedSecret, "configured" | "hint">): string {
  return secret.configured ? `••••••••${secret.hint ?? ""}` : "Not set";
}

export function fetchSecrets(): Promise<ManagedSecret[]> {
  return apiFetch<ManagedSecret[]>("/secrets");
}

export function testSecret(key: string): Promise<ManagedSecret> {
  return apiFetch<ManagedSecret>(`/secrets/${key}/test`, { method: "POST" });
}

export function saveSecret(key: string, value: string, twoFactorCode: string): Promise<ManagedSecret> {
  return apiFetch<ManagedSecret>(`/secrets/${key}`, { method: "PUT", body: JSON.stringify({ value, twoFactorCode }) });
}

export function clearSecret(key: string, twoFactorCode: string): Promise<ManagedSecret> {
  return apiFetch<ManagedSecret>(`/secrets/${key}`, { method: "DELETE", body: JSON.stringify({ twoFactorCode }) });
}
