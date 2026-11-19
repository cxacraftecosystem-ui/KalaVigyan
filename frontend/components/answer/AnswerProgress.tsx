import type { AnswerStatus } from "@/lib/types";

export function AnswerProgress({ status, writing }: { status: AnswerStatus | null; writing: boolean }) {
  const message = status?.message ?? (writing ? "Writing" : "Starting");
  return (
    <p className="flex items-center gap-2 font-ui text-ui text-ink-3" role="status" aria-live="polite" data-testid="answer-progress" data-step={status?.step}>
      <span className="kv-spin shrink-0" aria-hidden />
      <span>{message}…</span>
    </p>
  );
}
