import { motionAllowedNow } from "@/components/motion/useMotionAllowed";

export function scrollToAnchor(id: string): void {
  if (typeof document === "undefined") return;
  document.getElementById(id)?.scrollIntoView({ behavior: motionAllowedNow() ? "smooth" : "auto", block: "start" });
}
