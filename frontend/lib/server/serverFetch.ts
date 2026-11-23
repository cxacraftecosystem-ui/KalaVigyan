import {
  PROXY_SECRET_HEADER,
  VIEWER_ADDRESS_HEADER,
  apiOrigin,
  cookieNames,
  isSecureRequest,
  proxySecret,
  viewerOrUnknown
} from "@/lib/server/apiProxy";

export const SERVER_FETCH_TIMEOUT_MS = 4_000;
export const PUBLIC_REVALIDATE_SECONDS = 3_600;
const NOT_FOUND = 404;

export type ServerFetchFailure = "unconfigured" | "timeout" | "unreachable" | "refused" | "failed" | "invalid";

export type ServerFetchResult<T> = { ok: true; body: T } | { ok: false; failure: ServerFetchFailure; status: number | null };

export function bodyOrAbsent<T>(result: ServerFetchResult<T>, unavailable: string): T | null {
  if (result.ok) return result.body;
  if (result.status === NOT_FOUND) return null;
  throw new Error(`${unavailable}: ${result.failure}`);
}

type Env = Record<string, string | undefined>;

export type ServerFetchDeps = { fetcher: typeof fetch; env: Env; timeoutMs: number };

export type IncomingRequest = { headers: Headers; cookie: (name: string) => string | null };

export type PublicFetchOptions<T> = {
  parse: (body: unknown) => T;
  tags: readonly string[];
  revalidateSeconds?: number;
  deps?: Partial<ServerFetchDeps>;
};

export type SignedInFetchOptions<T> = {
  parse: (body: unknown) => T;
  request?: IncomingRequest;
  deps?: Partial<ServerFetchDeps>;
};

export async function publicFetch<T>(path: string, options: PublicFetchOptions<T>): Promise<ServerFetchResult<T>> {
  const deps = withDefaults(options.deps);
  const init: RequestInit = {
    headers: serviceHeaders(deps.env),
    next: { tags: [...options.tags], revalidate: options.revalidateSeconds ?? PUBLIC_REVALIDATE_SECONDS }
  };
  return fetchFromApi(path, init, options.parse, deps);
}

export async function signedInFetch<T>(path: string, options: SignedInFetchOptions<T>): Promise<ServerFetchResult<T>> {
  const deps = withDefaults(options.deps);
  const request = options.request ?? (await incomingRequest());
  const token = request.cookie(cookieNames(isSecureRequest(request.headers, null)).session);
  if (!token) return { ok: false, failure: "refused", status: 401 };
  const headers = serviceHeaders(deps.env);
  headers.set("authorization", `Bearer ${token}`);
  if (headers.has(PROXY_SECRET_HEADER)) headers.set(VIEWER_ADDRESS_HEADER, viewerOrUnknown(request.headers));
  return fetchFromApi(path, { headers, cache: "no-store" }, options.parse, deps);
}

export async function incomingRequest(): Promise<IncomingRequest> {
  const { cookies, headers } = await import("next/headers");
  const [jar, incoming] = await Promise.all([cookies(), headers()]);
  return { headers: new Headers(incoming), cookie: (name) => jar.get(name)?.value || null };
}

function withDefaults(deps: Partial<ServerFetchDeps> = {}): ServerFetchDeps {
  return {
    fetcher: deps.fetcher ?? fetch,
    env: deps.env ?? (process.env as Env),
    timeoutMs: deps.timeoutMs ?? SERVER_FETCH_TIMEOUT_MS
  };
}

function serviceHeaders(env: Env): Headers {
  const headers = new Headers({ accept: "application/json" });
  const secret = proxySecret(env);
  if (secret) headers.set(PROXY_SECRET_HEADER, secret);
  return headers;
}

async function fetchFromApi<T>(path: string, init: RequestInit, parse: (body: unknown) => T, deps: ServerFetchDeps): Promise<ServerFetchResult<T>> {
  const origin = apiOrigin(deps.env);
  if (!origin) return { ok: false, failure: "unconfigured", status: null };
  let response: Response;
  try {
    response = await deps.fetcher(`${origin}/api${path}`, { ...init, redirect: "manual", signal: AbortSignal.timeout(deps.timeoutMs) });
  } catch (error) {
    return { ok: false, failure: timedOut(error) ? "timeout" : "unreachable", status: null };
  }
  if (response.status === 401 || response.status === 403) return { ok: false, failure: "refused", status: response.status };
  if (!response.ok) return { ok: false, failure: "failed", status: response.status };
  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    return { ok: false, failure: timedOut(error) ? "timeout" : "invalid", status: response.status };
  }
  try {
    return { ok: true, body: parse(body) };
  } catch (error) {
    console.error(`server fetch of ${path} is off its contract`, error);
    return { ok: false, failure: "invalid", status: response.status };
  }
}

function timedOut(error: unknown): boolean {
  return error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError");
}
