import { NextResponse, type NextRequest } from "next/server";

import {
  apiOrigin,
  csrfRefusal,
  isMachineRoute,
  MACHINE_RESPONSE_HEADERS,
  refuseCrossSite,
  refuseUnconfigured,
  sessionTokenOf,
  upstreamHeaders,
  upstreamUrl
} from "@/lib/server/apiProxy";
import { REVALIDATE_ROUTE } from "@/lib/server/revalidation";

const SESSION_ROUTES = new Set([
  "/api/auth/login",
  "/api/auth/two-factor/verify",
  "/api/auth/change-password",
  "/api/auth/logout",
  "/api/session/adopt",
  "/api/session/end",
  REVALIDATE_ROUTE
]);

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (SESSION_ROUTES.has(path)) return NextResponse.next();
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
