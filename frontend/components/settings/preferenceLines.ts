import type { SegmentOption } from "@/components/ui/SegmentedChoice";
import type { ContrastChoice, ResolvedTheme, ThemeChoice } from "@/lib/preferences";

export const THEME_OPTIONS: SegmentOption[] = [
  { value: "system", label: "Match my device" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" }
];

export const CONTRAST_OPTIONS: SegmentOption[] = [
  { value: "system", label: "Match my device" },
  { value: "standard", label: "Standard" },
  { value: "high", label: "High" }
];

export const TEXT_OPTIONS: SegmentOption[] = [
  { value: "standard", label: "Standard" },
  { value: "larger", label: "Larger" }
];

export const MOTION_OPTIONS: SegmentOption[] = [
  { value: "device", label: "Match my device" },
  { value: "reduced", label: "Reduced" }
];

export function themeLine(choice: ThemeChoice, resolved: ResolvedTheme): string {
  const name = resolved === "dark" ? "Dark" : "Light";
  if (choice === "system") return `${name} now, because your device is set to ${resolved}.`;
  return `${name} on every device, whatever the device is set to.`;
}

export function contrastLine(choice: ContrastChoice, deviceAsksForMore: boolean): string {
  if (choice === "high") return "High: darker text, stronger edges and a thicker focus ring, on every device.";
  if (choice === "standard") return deviceAsksForMore ? "Standard, although your device asks for more contrast." : "Standard, even when a device asks for more contrast.";
  return deviceAsksForMore ? "High now, because your device asks for more contrast." : "Standard now. High contrast comes on when your device asks for more.";
}

export function textLine(larger: boolean): string {
  return larger ? "Larger: every size is an eighth bigger, at every width." : "Standard sizes. Larger makes every size an eighth bigger.";
}

export function motionLine(reduced: boolean, deviceAsksForLess: boolean): string {
  if (reduced) return "Reduced: every animation shows its end state at once.";
  return deviceAsksForLess ? "Reduced now, because your device asks for less motion." : "Full. Animations only explain a process, and always end still.";
}
