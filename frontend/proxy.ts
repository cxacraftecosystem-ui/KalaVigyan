import { NextResponse, type NextRequest } from "next/server";

import {
  apiOrigin,
  csrfRefusal,
  isAccountWrite,
  isMachineRoute,
  MACHINE_RESPONSE_HEADERS,
  refuseCrossSite,
  refuseUnconfigured,
  sessionTokenOf,
  upstreamHeaders,
  upstreamUrl
} from "@/lib/server/apiProxy";
import { REVALIDATE_ROUTE } from "@/lib/server/revalidation";
import { SESSION_ADOPT_PATH, SESSION_END_PATH, SESSION_RENEW_PATH } from "@/lib/sessionCookie";

const WEB_ROUTES = new Set([SESSION_ADOPT_PATH, SESSION_END_PATH, SESSION_RENEW_PATH, "/api/version", REVALIDATE_ROUTE]);

function answeredByTheWeb(path: string, method: string): boolean {
  return WEB_ROUTES.has(path) || isAccountWrite(path, method);
}

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (answeredByTheWeb(path, request.method)) return NextResponse.next();
  const machine = isMachineRoute(path);
  if (!machine && csrfRefusal(request)) return refuseCrossSite();
  const origin = apiOrigin();
  if (!origin) return refuseUnconfigured();
  const headers = upstreamHeaders(request, machine ? null : sessionTokenOf(request));
  const response = NextResponse.rewrite(new URL(upstreamUrl(request, origin)), { request: { headers } });
  response.headers.set("x-vercel-enable-rewrite-caching", "0");
  if (machine) for (const [name, value] of Object.entries(MACHINE_RESPONSE_HEADERS)) response.headers.set(name, value);
  return response;
}

export const config = {
  matcher: "/api/:path*"
};
