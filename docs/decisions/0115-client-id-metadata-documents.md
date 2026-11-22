# 0115. MCP clients sign in with their published identity

An MCP client may sign in with its published identity: a `client_id` holding `://` is the address of
a client ID metadata document, read through the fetcher and held within a bound. Errors stop on
KalaVigyan's page, each published client has one stored row, and people see who is asking.

Date: 2026-11-21. Status: accepted (owner, 2026-11-20: "every MCP gap is to be resolved, each and
every one"). Amends decision 0101 item 15 ("Authentication") and `docs/contracts/mcp-oauth.md`;
dynamic client registration stays as it was.

| For | Read |
|---|---|
| What it amends | [0101 One knowledge architecture for every craft: facts, sections, components, monographs](0101-knowledge-architecture-for-every-craft.md): item 15, Authentication, for published client identities |
| What it amends | [mcp-oauth.md](../contracts/mcp-oauth.md); dynamic client registration stays as it was |
| Later changed by | [0148](0148-a-client-that-can-sign-in-publicly-is-signed-in-publicly.md): a document listing `none` among its supported methods signs in as a public client |
| Every decision, by group | [README.md](README.md) |

## Context

Claude's custom-connector dialog offers three OAuth clients and recommends the first: "Use Claude's
published identity (Recommended)", then "Register automatically", then "Use your own OAuth client".
The published identity is an OAuth client ID metadata document: the client's `client_id` is an https
URL, and the JSON document at that URL names the client and its redirect URIs. The MCP authorization
specification of 2025-11-25 says authorization servers and clients SHOULD support these documents
(draft-ietf-oauth-client-id-metadata-document), MAY support dynamic registration, and that a client
SHOULD prefer a document when the server metadata says
`client_id_metadata_document_supported: true`. KalaVigyan advertised only registration, so the
Connect your AI page told people to pick the second option, and every connection left one more
registered client behind for the nightly upkeep to clear.

Two published documents were read on 2026-11-21:

- Claude, `https://claude.ai/oauth/mcp-oauth-client-metadata`: `client_name` Claude, one redirect
  URI `https://claude.ai/api/mcp/auth_callback`, `token_endpoint_auth_method` none, and
  `grant_types` that include a JWT bearer grant KalaVigyan does not offer.
- VS Code, `https://vscode.dev/oauth/client-metadata.json`: a loopback redirect
  `http://127.0.0.1:33418/` beside `https://vscode.dev/redirect`, `token_endpoint_auth_method` none.

## Decision

1. **A `client_id` that holds `://` is a client ID metadata document address.** It must be https on
   port 443, with a host, a path other than `/` and no `.` or `..` segments, no user name, password
   or fragment, and at most 2,048 characters (`research/oauth_client_documents.client_id_problem`).
   Anything else is refused as `invalid_client` before anything is fetched.
2. **The document is read through the fetcher, never by the API.** The fetcher process
   (`kv-fetcher`, decision 0007) gains `POST /fetch-client-document`
   (`fetcher/client_documents.py`): https only, the host's addresses resolved and refused when any
   is private, loopback, link-local or a cloud metadata address, the connection pinned to the
   vetted address, at most 5 KB (the draft's recommendation), at most 5 seconds, `Accept:
   application/json`, no robots check (the client asked us to read it), and no redirect followed at
   all (the draft's latest revision says MUST NOT; a redirect to another host is the case the lane
   named). The answer passes the document's `Cache-Control` back in
   `X-Client-Document-Cache-Control`. The unit's `IPAddressDeny` keeps the private ranges closed
   underneath.
3. **What a document must hold** (`research/oauth_client_documents.metadata_client`): a JSON
   object whose `client_id` is exactly the address it was read from (simple string comparison), a
   `client_name` of 1 to 120 characters, 1 to 10 `redirect_uris` that each pass the redirect rule a
   registered client's must pass (https with a host, http on 127.0.0.1, [::1] or localhost, or a
   native app's own scheme; never a fragment or a refused scheme), no `client_secret` or
   `client_secret_expires_at`, and a `token_endpoint_auth_method` that is absent or `none` (and a
   `token_endpoint_auth_methods_supported`, when given, that includes `none`). Grant and response
   types it lists are not judged: KalaVigyan issues only codes and refresh tokens whatever a client
   can do elsewhere. Any break is `invalid_client`.
4. **Held, within a bound.** The API holds each good document in its process for `max-age` from its
   `Cache-Control`, at least a minute and at most a day; a document without `max-age` is held ten
   minutes, and `no-store` or `no-cache` a minute, so one consent (its review, then its approval)
   reads it once. At most 256 documents are held, the least recently used leaving first. A refusal,
   a failure or a document that breaks a rule is never held (`services/oauth_client_documents.py`).
5. **Errors stop on KalaVigyan's page, never at the client.** The consent routes answer 400 with
   the reason (`invalid_client`) for a refused address, a private address, a document too large, a
   redirect, a missing document or one that breaks a rule, and 503 (`temporarily_unavailable`) when
   the document was too slow, its host failed or was rate limited, or the fetcher could not be
   reached. Nothing is sent to the client's redirect URI until the document has vouched for it.
6. **One stored row per published client.** At approval the API keeps an `OAuthClient` row whose id
   is the UUID version 5 of the `client_id` address (`uuid5(NAMESPACE_URL, url)`), whose name and
   redirect URIs are the document's and whose `clientUri` is the `client_id` address; each approval
   refreshes them and its `createdAt`, so the 30-day upkeep removes only a row nobody approved for a
   month. Codes and connections point at that row exactly as at a registered client's, so PKCE S256,
   the exact redirect match (a loopback port may differ), the token, refresh, revocation and bearer
   rules, the roster (only an admitted account can sign in to consent), the terms and the scopes by
   role are unchanged. No migration: the row fits the table as it is. The token and revocation
   endpoints know a published client by its address alone; the UUID of such a row is refused as a
   `client_id`, and registered clients keep their random version 4 UUIDs.
7. **People see who is asking.** The prompt carries `clientIdHost`, the host of the `client_id`
   (null for a registered client). The consent page shows a Who is asking grid (App, Identity:
   "Published at claude.ai" or "Registered by the app itself", Returns you to, Asks to) and, when
   the return address is a program on this computer (localhost, 127.x, [::1]), a warning to approve
   only a sign-in the person started from that app, as the specification asks for loopback
   redirects. Settings shows a published client by its `client_id` host.
8. **Metadata.** The authorization server metadata adds `client_id_metadata_document_supported:
   true`; `registration_endpoint` and everything else stay. The Connect your AI page tells Claude
   users to choose "Use Claude's published identity (Recommended)", with Register automatically
   noted as the other way in.

## Consequences

- Claude, VS Code and any client that publishes its identity sign in without registering, and one
  row serves every person who connects that client; registration rows no longer grow with each
  Claude connector.
- Everyone who connects one published client shares its row, so a person connecting the same client
  twice still replaces their earlier connection (decision 0101's one row per app in Settings).
- A document's change reaches KalaVigyan within its `max-age` (a day at most); a connection already
  made is not ended by it.
- The fetcher must be running for a published client to sign in; while it is not, the consent page
  says to try again (503) and registered clients still sign in.
- Logos (`logo_uri`) are not fetched or shown; the draft asks a server that shows them to prefetch
  and serve them itself, which can come later.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
