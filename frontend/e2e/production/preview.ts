import type { BrowserContext } from "@playwright/test";

export const PRODUCTION_ORIGIN = "https://kalavigyan.vercel.app";
export const PREVIEW_HOST = /^kalavigyan-[a-z0-9]{9}-cxacraftecosystem-8028s-projects\.vercel\.app$/;
export const BYPASS_HEADER = "x-vercel-protection-bypass";
export const SET_BYPASS_COOKIE_HEADER = "x-vercel-set-bypass-cookie";
export const VERCEL_TOOLBAR_URLS = "https://vercel.live/*";
export const GOOGLE_ORIGIN_REFUSED = "[GSI_LOGGER]: The given origin is not allowed for the given client ID.";
export const VERCEL_TOOLBAR_REFUSED = "Framing 'https://vercel.live/' violates the following Content Security Policy directive";
export const VERCEL_TOOLBAR_BLOCKED = "Refused to load https://vercel.live/";

const GOOGLE_SIGN_IN = "https://accounts.google.com/gsi/";
const FAILED_RESOURCE = "Failed to load resource";

function parsed(url: string): URL | null {
  try {
    return new URL(url);
  } catch {
    return null;
  }
}

export function isPreview(url: string): boolean {
  const site = parsed(url);
  return site !== null && site.protocol === "https:" && site.port === "" && !site.username && !site.password && PREVIEW_HOST.test(site.hostname);
}

export function isProduction(url: string): boolean {
  return parsed(url)?.origin === PRODUCTION_ORIGIN;
}

export function roleSiteRefusal(url: string): string | null {
  if (isProduction(url)) return null;
  return `The Professor and Admin accounts sign in only on ${PRODUCTION_ORIGIN}, never on ${url}, which can be built from any branch.`;
}

export function googleRefusesPreview(text: string, from: string): boolean {
  return text.startsWith(GOOGLE_ORIGIN_REFUSED) || (text.startsWith(FAILED_RESOURCE) && from.startsWith(GOOGLE_SIGN_IN));
}

export function previewConsoleNoise(text: string, from: string): boolean {
  return googleRefusesPreview(text, from) || text.startsWith(VERCEL_TOOLBAR_REFUSED) || text.startsWith(VERCEL_TOOLBAR_BLOCKED);
}

export function previewBlockedUrls(url: string): string[] {
  return isPreview(url) ? [VERCEL_TOOLBAR_URLS] : [];
}

export function siteRefusal(url: string): string | null {
  if (isProduction(url) || isPreview(url)) return null;
  return `E2E_BASE_URL must be ${PRODUCTION_ORIGIN} or one of its Vercel previews (https://kalavigyan-<id>-cxacraftecosystem-8028s-projects.vercel.app), not ${url}`;
}

export async function passPreviewProtection(context: BrowserContext, url: string, token: string): Promise<void> {
  if (!token || !isPreview(url)) return;
  const origin = new URL(url).origin;
  const response = await context.request.get(`${origin}/`, {
    headers: { [BYPASS_HEADER]: token, [SET_BYPASS_COOKIE_HEADER]: "true" },
    maxRedirects: 0,
    failOnStatusCode: false
  });
  const location = response.headers()["location"];
  const leaves = location ? new URL(location, origin).origin !== origin : false;
  if (response.status() >= 400 || leaves) throw new Error(`the preview refused the protection bypass with ${response.status()}`);
}
