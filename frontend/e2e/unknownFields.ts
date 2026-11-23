export const UNKNOWN_FIELD = "fieldThisBuildDoesNotKnow";
export const UNKNOWN_VALUE = "a field a later backend added";

export function withUnknownFields(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(withUnknownFields);
  if (typeof value !== "object" || value === null) return value;
  const out: Record<string, unknown> = { [UNKNOWN_FIELD]: UNKNOWN_VALUE };
  for (const [name, entry] of Object.entries(value)) out[name] = withUnknownFields(entry);
  return out;
}
