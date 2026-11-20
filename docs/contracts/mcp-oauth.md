# MCP sign-in (OAuth 2.1)

Slice 2 of the MCP server (decision 0101, item 15, "Authentication" and "Guards"). An agent's
MCP client signs a person in with OAuth 2.1 as the MCP authorization specification defines
(2025-06-18 and 2025-11-25): protected resource metadata (RFC 9728), authorization server
metadata (RFC 8414), dynamic client registration (RFC 7591), the authorization code grant with
PKCE S256 only, rotating refresh tokens, token revocation (RFC 7009), resource indicators
(RFC 8707) and the `iss` response parameter (RFC 9207). The read tools and the protocol are in
`docs/contracts/knowledge-api.md`; nothing there changes for a call without a token.

## Hosts

- **The API** is `PUBLIC_API_URL` (CloudFront in front of nginx, which forwards every path to
  FastAPI). It is the issuer and serves the metadata, registration, token and revocation
  endpoints, and the MCP server itself at `/api/mcp`.
- **The web app** is `PUBLIC_WEB_URL` (Vercel). It serves the consent screen at
  `/oauth/authorize`, the one step a person sees. Its proxy (`frontend/proxy.ts`) forwards only
  `/api/*` and refuses a POST that is not same-origin, so an agent's server-to-server token call
  cannot pass through it, and `next.config.ts` rewrites nothing under `/.well-known`. That is why
  the issuer and its endpoints live on the API origin while the authorization endpoint is the web
  page.
- Both must be an https origin (http only on a loopback host, for development). Without them the
  metadata, token and bearer paths answer 503 and anonymous reads go on as before.
- Everything is off while `MCP_SERVER_ENABLED` is false (404), except Settings' list of connected
  apps and Revoke, which always work.

| What | URL |
|---|---|
| MCP server (the resource) | `<API>/api/mcp` |
| Protected resource metadata | `<API>/.well-known/oauth-protected-resource/api/mcp`, also at `<API>/.well-known/oauth-protected-resource` |
| Authorization server metadata (issuer `<API>`) | `<API>/.well-known/oauth-authorization-server` |
| Authorization endpoint | `<WEB>/oauth/authorize` |
| Token endpoint | `<API>/api/oauth/token` |
| Registration endpoint | `<API>/api/oauth/register` |
| Revocation endpoint | `<API>/api/oauth/revoke` |

The metadata documents are public and cached five minutes. They, the registration, token and
revocation endpoints and `/api/mcp` answer browser clients from any origin without credentials,
preflight included (`api/mcp_cors.py`, `knowledge-api.md`), as the MCP authorization specification
expects of clients that run in a browser; the consent routes keep the site's configured origins. The authorization server metadata lists `scopes_supported`
(read, ask, contribute, review), `response_types_supported` `code`, `grant_types_supported`
`authorization_code` and `refresh_token`, `token_endpoint_auth_methods_supported` and
`revocation_endpoint_auth_methods_supported` `none`, `code_challenge_methods_supported` `S256`
and `authorization_response_iss_parameter_supported` true.

## Registration

`POST /api/oauth/register`, JSON (RFC 7591). Public clients only.

- `redirect_uris` (1 to 10) each must be https with a host, http on 127.0.0.1, [::1] or
  localhost, or a native app's own scheme (`cursor://…`). No fragment, no user name, never
  `javascript`, `data`, `file`, `vbscript`, `about`, `blob`, `filesystem` or `ftp`.
- `grant_types` within `authorization_code`, `refresh_token`; `response_types` within `code`;
  `token_endpoint_auth_method` absent or `none`; `client_uri` https. Unknown fields are ignored.
- `201` with `client_id` (a UUID), `client_id_issued_at`, `client_name` (the first redirect's
  host when none is given), `redirect_uris`, `grant_types` (both), `response_types`,
  `token_endpoint_auth_method: none`.
- Errors are `400 {error, error_description}` with `invalid_redirect_uri` or
  `invalid_client_metadata`. At most 20 registrations an hour from one address
  (`core/rate_limit.client_registration_attempt`), then 429 with `Retry-After`.
- A client registered more than 30 days ago that never completed a sign-in (no connection, so no
  token; an unexchanged code goes with it) is removed by the nightly upkeep, at most 1,000 a night
  (`services/upkeep_clients.py`, `ABANDONED_CLIENT_AGE`, `ABANDONED_CLIENTS_PER_NIGHT`; counted in
  the report's `clients.abandonedRemoved`, `nightly-upkeep.md`). Its `client_id` then answers as an
  unknown client.

## Authorization

The client sends the person to `<WEB>/oauth/authorize` with `response_type=code`, `client_id`,
`redirect_uri`, `code_challenge`, `code_challenge_method=S256`, `state`, `scope` and `resource`.

1. The page sits in the signed-in shell: a signed-out person signs in with today's sign-in
   (including two-step verification and a forced password change) and comes back to the same URL.
2. It sends the OAuth parameters, and only those, to `GET /api/oauth/authorize/request`.
   - An unknown `client_id`, or a `redirect_uri` the client did not register, answers 400 and the
     page stops there: nothing is sent to an address nobody vouched for. A loopback redirect may
     differ from the registered one only in its port (RFC 8252).
   - Any other fault (`response_type` not `code`, no S256 challenge, a malformed challenge,
     `state` over 1,024 characters, an unknown scope, a `resource` that is not this server)
     answers `{kind: "redirect", redirectTo}` carrying `error`, `error_description`, `state` and
     `iss`. The page shows that nothing was connected and returns only when the person presses
     Return to the app, so a registered client cannot use the page as an open redirector
     (RFC 9700, 4.11).
   - Otherwise `{kind: "prompt", clientName, redirectHost, scopes[{scope, title, description,
     allowed, needs}], terms{version, acceptedAt}}`.
3. The person reads the scopes (read is always given; a scope their role cannot hold is shown
   with what it needs and cannot be ticked), reads and accepts the MCP terms of use when this
   version is not yet accepted, and presses Approve or Cancel (an `ActionGroup`).
4. Approve posts `POST /api/oauth/authorize/approve {request, scopes, termsVersion}`. The request
   is checked again; a scope not asked for or not held by the role is 422, a terms version that
   is not the current one 409. The acceptance is recorded, a code is stored and the reply is
   `{kind: "redirect", redirectTo: <redirect_uri>?code&state&iss}`, which the page opens.
   Cancel posts `POST /api/oauth/authorize/deny {request}` and returns `error=access_denied`.

A missing `scope` asks for read. `resource`, when sent, must be `<API>/api/mcp` (a trailing slash
is ignored); when absent it is taken to be that.

## Tokens

`POST /api/oauth/token`, `application/x-www-form-urlencoded`, each parameter at most once, an
empty value treated as absent. `client_id` is required and `client_secret` refused.

- `grant_type=authorization_code` with `code`, `redirect_uri` (exactly the one the code was
  issued for), `code_verifier` (43 to 128 unreserved characters whose base64url SHA-256 is the
  challenge) and optional `resource`. A code lives 5 minutes and works once: a second use is
  refused and revokes the connection it made.
- `grant_type=refresh_token` with `refresh_token`, optional `scope` (narrower only, else
  `invalid_scope`) and optional `resource`. Every refresh rotates: the old refresh token is
  spent, and presenting a spent one revokes the whole connection.
- The reply is `{access_token, token_type: "Bearer", expires_in: 3600, refresh_token, scope}`
  with `Cache-Control: no-store` and `Pragma: no-cache`. Access tokens live an hour, refresh
  tokens 30 days from their issue, so a connection used at least monthly stays.
- Errors are RFC 6749 JSON: `invalid_request`, `invalid_client` (401), `invalid_grant`,
  `unsupported_grant_type`, `invalid_scope`, `invalid_target`.
- A second connection of the same app by the same person revokes the first, so Settings lists one
  row per app.

`POST /api/oauth/revoke` (RFC 7009), form, `token` and `client_id`: a refresh token revokes its
connection, an access token only itself. An unknown token, or one of another client, answers
200 and changes nothing.

## The bearer on the MCP server

`POST /api/mcp` with `Authorization: Bearer <access token>`:

- The token must be ours, unrevoked, unexpired, issued for `<API>/api/mcp` and its account still
  live: not deleted, and its `tokenVersion` and `sessionsValidFrom` unchanged since the
  connection was made, so a password change, Sign out everywhere or a suspension ends every
  connection (`core/deps.token_matches_user`).
- Anything else is `401` with
  `WWW-Authenticate: Bearer error="invalid_token", error_description="…", resource_metadata="<API>/.well-known/oauth-protected-resource/api/mcp"`,
  and the attempt counts against the address's anonymous limit. A header that is not Bearer is
  refused the same way.
- The account and its scopes go on `ToolContext` (`user`, `scopes`). The scopes are the token's,
  less any the account's role no longer holds.
- A tool needing more than read: without a token the call is `401` with
  `WWW-Authenticate: Bearer scope="read <scope>", resource_metadata="…"`, which starts the
  client's sign-in; with a token lacking the scope it is `403` with
  `error="insufficient_scope"` and the scopes to ask for.
- No token stays an anonymous read, counted per address as today.

## Scopes and roles

| Scope | Who may give it | Lets the agent |
|---|---|---|
| `read` | everyone, always given | read what a signed-out reader sees |
| `ask` | `ASK_STANDARD` (every role) | ask and receive cited answers in the person's name |
| `contribute` | `PROPOSE_KNOWLEDGE` (Researcher and above) | propose facts (one or up to 25 at once) and follow them (`get_proposal`), sources, structure, layouts and components; claim and release tasks and list its own (`my_tasks`); steward crafts (`adopt_craft`, `drop_craft`, `my_crafts`) |
| `review` | Professor, Admin, Master Admin | review proposals |

The rule is `research/oauth_rules.may_hold`; the words shown are `research/oauth_contract.SCOPE_TEXT`.

## Terms of use

- The one copy of the text is `backend/app/data/mcp_terms_of_use.md`, version `MCP_TERMS_VERSION`
  (`2026-11-19`, `research/oauth_rules.py`); `docs/legal/mcp-terms-of-use.md` keeps the approval and
  points to it, and `tests/mcp/test_mcp_terms_copy.py` holds the pointer and keeps the text out of
  it. `GET /api/oauth/terms` answers `{version, title, body}`.
- Acceptance is a `McpTermsAcceptance` row per account and version. A new version is asked for at
  the next authorization; a connection already made is not ended by it.

## Settings

`GET /api/oauth/connections` answers `{serverUrl, connections[{id, clientName, clientHost,
scopes, connectedAt, lastUsedAt}]}`, the person's unrevoked, unexpired connections, newest first;
`serverUrl` is the MCP server's URL while it is on and null otherwise.
`DELETE /api/oauth/connections/{id}` revokes one of the person's own (204), else 404. The card
is `components/settings/ConnectedClientsCard.tsx`; it hides itself while the server is off and
nothing is connected.

## Guards

- **Rate limit per connection**: 1,200 calls in 10 minutes for one connection, counted across its
  rotated tokens so a refresh does not reset it, then 429 with `Retry-After`
  (`core/rate_limit.mcp_connection_attempt`). It protects the service and is not a spend cap.
- **Audit**: each `tools/call` with a token writes `McpToolCall {grantId, tokenId, tool, outcome,
  calledAt}`, outcome `OK`, `TOOL_ERROR` or `PROTOCOL_ERROR`. A name that is not a tool is
  stored as `(unknown)`. Arguments and results are never stored. `OAuthGrant.lastUsedAt` moves at
  most once a minute.

## Storage

Migration `0037_oauth`: `OAuthClient`, `OAuthGrant` (a connection: client, account, scopes,
resource, the account's token version, connected, last used, expires, revoked), `OAuthCode`,
`OAuthToken` (`ACCESS` or `REFRESH`, with its scopes), `McpTermsAcceptance`, `McpToolCall`, all
with row-level security on and no grants to `anon` or `authenticated`. Codes and tokens are
random (`kvmcp_ac_`, `kvmcp_at_`, `kvmcp_rt_` and 32 random bytes) and stored only as their
SHA-256; they are never logged.

## Code

- Contracts: `research/oauth_rules.py` (PKCE, redirect URIs, scopes, lifetimes, errors),
  `research/oauth_contract.py` (bodies and replies), `research/oauth_authorization.py` (checking a
  request, granting scopes, the redirects), `research/oauth_metadata.py` (the two documents and
  the challenge header).
- Services: `oauth_clients`, `oauth_consent`, `oauth_tokens`, `oauth_bearer`,
  `oauth_connections`.
- Routes: `api/routes/oauth_well_known.py`, `api/routes/oauth.py`, `api/routes/oauth_consent.py`,
  `api/routes/mcp.py`; `api/oauth_hosts.py` (paths and URLs), `api/oauth_wire.py` (form and error
  bodies), `api/mcp_auth.py` (the bearer, the challenges and the audit), `api/mcp_cors.py` (browser
  clients); the clean-up `services/upkeep_clients.py`.
- Web: `app/oauth/authorize/page.tsx`, `components/oauth/*`, `lib/oauthContract.ts`,
  `lib/oauthConsent.ts`.
