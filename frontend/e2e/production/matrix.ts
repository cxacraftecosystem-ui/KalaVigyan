import { devices, type BrowserContextOptions } from "@playwright/test";

export type Scheme = "light" | "dark";

export type Width = {
  key: string;
  label: string;
  device: keyof typeof devices;
  viewport: { width: number; height: number };
};

export const SCHEMES: readonly Scheme[] = ["light", "dark"];
export const FAKE_MICROPHONE_ARGS = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"];

export const WIDE: Width = { key: "wide", label: "Wide 1920", device: "Desktop Chrome", viewport: { width: 1920, height: 1080 } };
export const DESKTOP: Width = { key: "desktop", label: "Desktop 1440", device: "Desktop Chrome", viewport: { width: 1440, height: 900 } };
export const TABLET: Width = { key: "tablet", label: "Tablet 834", device: "Galaxy Tab S9", viewport: { width: 834, height: 1194 } };
export const PHONE: Width = { key: "phone", label: "Phone 390", device: "Pixel 7", viewport: { width: 390, height: 844 } };
export const SMALL_PHONE: Width = { key: "small-phone", label: "Phone 360", device: "Pixel 7", viewport: { width: 360, height: 800 } };
export const IPHONE: Width = { key: "iphone", label: "iPhone", device: "iPhone 17", viewport: devices["iPhone 17"].viewport };

export const SCREEN_WIDTHS: readonly Width[] = [WIDE, DESKTOP, TABLET, PHONE, SMALL_PHONE];
export const ANSWER_WIDTHS: readonly Width[] = [TABLET, PHONE];
export const ANONYMOUS_WIDTHS: readonly Width[] = [SMALL_PHONE, TABLET, DESKTOP];
export const QUESTIONS_WIDTH = DESKTOP;
export const QUESTIONS_SCHEME: Scheme = "light";

const SCHEME_LABEL: Record<Scheme, string> = { light: "Light", dark: "Dark" };

export function runLabel(width: Width, scheme: Scheme): string {
  return `${width.label} ${SCHEME_LABEL[scheme]}`;
}

export function projectName(width: Width, scheme: Scheme): string {
  return `production-${width.key}-${scheme}`;
}

export function anonymousProjectName(width: Width): string {
  return `production-anonymous-${width.key}`;
}

export function contextOptions(width: Width, scheme: Scheme): BrowserContextOptions {
  return {
    ...devices[width.device],
    viewport: width.viewport,
    screen: width.viewport,
    colorScheme: scheme,
    locale: "en-IN",
    timezoneId: "Asia/Kolkata"
  };
}
