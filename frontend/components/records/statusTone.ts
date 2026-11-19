import { CheckCircle2, CircleDashed, Clock, Info, OctagonAlert, TriangleAlert, type LucideIcon } from "lucide-react";

export type StatusTone = "success" | "waiting" | "warning" | "error" | "info" | "neutral";

export const STATUS_TONES: Record<StatusTone, { icon: LucideIcon; ink: string; wash: string }> = {
  success: { icon: CheckCircle2, ink: "text-success", wash: "bg-success-wash" },
  waiting: { icon: Clock, ink: "text-warning", wash: "bg-warning-wash" },
  warning: { icon: TriangleAlert, ink: "text-warning", wash: "bg-warning-wash" },
  error: { icon: OctagonAlert, ink: "text-error", wash: "bg-error-wash" },
  info: { icon: Info, ink: "text-info", wash: "bg-info-wash" },
  neutral: { icon: CircleDashed, ink: "text-ink-3", wash: "bg-sunk" }
};
