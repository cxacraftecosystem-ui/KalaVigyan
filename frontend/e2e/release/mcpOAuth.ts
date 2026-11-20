import { randomBytes } from "node:crypto";

import type {
  FetchLike,
  OAuthClientMetadata,
  OAuthClientProvider,
  OAuthDiscoveryState,
  StoredOAuthClientInformation,
  StoredOAuthTokens
} from "@modelcontextprotocol/client";

export const CLIENT_NAME = "KalaVigyan release gate";
export const CLIENT_SCOPE = "read";
export const REDIRECT_URI = "http://127.0.0.1:43117/callback";

export type Callback = { code: string; state: string | null; iss: string | null };

export type Exchange = { method: string; path: string; status: number; bearer: boolean };

export class MemoryOAuthProvider implements OAuthClientProvider {
  readonly expectedState = randomBytes(24).toString("base64url");
  authorizationUrl: URL | null = null;
  private client: StoredOAuthClientInformation | undefined;
  private held: StoredOAuthTokens | undefined;
  private verifier: string | undefined;
  private discovery: OAuthDiscoveryState | undefined;

  get redirectUrl(): string {
    return REDIRECT_URI;
  }

  get clientMetadata(): OAuthClientMetadata {
    return {
      client_name: CLIENT_NAME,
      redirect_uris: [REDIRECT_URI],
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
      scope: CLIENT_SCOPE
    };
  }

  state(): string {
    return this.expectedState;
  }

  clientInformation(): StoredOAuthClientInformation | undefined {
    return this.client;
  }

  saveClientInformation(information: StoredOAuthClientInformation): void {
    this.client = information;
  }

  tokens(): StoredOAuthTokens | undefined {
    return this.held;
  }

  saveTokens(tokens: StoredOAuthTokens): void {
    this.held = tokens;
  }

  redirectToAuthorization(authorizationUrl: URL): void {
    if (this.authorizationUrl) throw new Error(`the client was sent to sign in a second time (${authorizationUrl.origin}${authorizationUrl.pathname}); the first sign-in did not hold`);
    this.authorizationUrl = authorizationUrl;
  }

  saveCodeVerifier(codeVerifier: string): void {
    this.verifier = codeVerifier;
  }

  codeVerifier(): string {
    if (!this.verifier) throw new Error("the client holds no PKCE code verifier; the sign-in was never started");
    return this.verifier;
  }

  saveDiscoveryState(state: OAuthDiscoveryState): void {
    this.discovery = state;
  }

  discoveryState(): OAuthDiscoveryState | undefined {
    return this.discovery;
  }
}

export function callbackOf(redirectTo: string, redirectUri: string = REDIRECT_URI): Callback {
  const reached = new URL(redirectTo);
  const expected = new URL(redirectUri);
  if (`${reached.origin}${reached.pathname}` !== `${expected.origin}${expected.pathname}`) throw new Error(`the consent returned to ${reached.origin}${reached.pathname}, not the registered ${redirectUri}`);
  const refused = reached.searchParams.get("error");
  if (refused) throw new Error(`the consent answered ${refused}: ${reached.searchParams.get("error_description") ?? "no description"}`);
  const code = reached.searchParams.get("code");
  if (!code) throw new Error("the consent returned without an authorization code");
  return { code, state: reached.searchParams.get("state"), iss: reached.searchParams.get("iss") };
}

export class ExchangeLog {
  readonly exchanges: Exchange[] = [];

  readonly fetch: FetchLike = async (url, init) => {
    const response = await fetch(url, init);
    const headers = new Headers(init?.headers);
    this.exchanges.push({ method: init?.method ?? "GET", path: new URL(url).pathname, status: response.status, bearer: (headers.get("authorization") ?? "").startsWith("Bearer ") });
    return response;
  };

  to(path: string): Exchange[] {
    return this.exchanges.filter((exchange) => exchange.path === path);
  }
}
