# 0148. A client that can sign in publicly is signed in publicly

A client ID metadata document that lists `none` among the token endpoint methods it supports is
signed in as a public client with PKCE, whatever method it prefers.

Date: 2026-11-22. Status: accepted (the lead, on the owner's report of 2026-11-22 that ChatGPT
could not connect). It amends [decision 0115](0115-client-id-metadata-documents.md). The contract
is `docs/contracts/mcp-oauth.md`, the client's document.

| For | Read |
|---|---|
| The rule it amends | [decision 0115](0115-client-id-metadata-documents.md) |
| The document rules | [mcp-oauth.md](../contracts/mcp-oauth.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Claude names itself by `https://claude.ai/oauth/mcp-oauth-client-metadata`, whose document says
`token_endpoint_auth_method: none`, and connects. ChatGPT names itself by
`https://chatgpt.com/oauth/client.json`, whose document prefers `private_key_jwt` (with a
`jwks_uri`) but lists `token_endpoint_auth_methods_supported: ["none", "private_key_jwt"]`.
Decision 0115 refused any document whose preferred method was not `none`, so ChatGPT's sign-in
stopped at the authorization request with "The client's metadata document asks for client
authentication". KalaVigyan's server metadata offers only `none`, so a client that supports it
has what it needs.

## Decision

1. **The supported list decides.** When a document gives `token_endpoint_auth_methods_supported`,
   it is accepted if the list includes `none`, whatever `token_endpoint_auth_method` prefers; when
   it gives no list, `token_endpoint_auth_method` must be absent or `none`, as before.
2. **Still public only.** Such a client is signed in exactly as any public client: PKCE with S256,
   the return address read from its own document, no client secret held or issued. A signed client
   assertion a client sends anyway gives it nothing; when the token request carries no
   `client_id`, the assertion's `sub` (equal to its `iss`) names the client
   (`research/oauth_client_documents.named_client_id`), which is safe unverified because the code
   is still bound to that client, its return address and its PKCE verifier.
3. **Signed assertions are not verified.** Verifying `private_key_jwt` against the client's
   `jwks_uri` would add a second proof of the client beyond PKCE and the document's own return
   address; it is not needed for a public sign-in and is not built.

## Consequences

- ChatGPT connects through its published identity; Claude, VS Code and Cursor are unchanged.
- A document that cannot sign in as a public client (no `none` in its list, or a preferred
  confidential method with no list) is still refused as `invalid_client`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record
that names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in the [contracts](../contracts/README.md). Its rules are
tested by `backend/tests/mcp/test_oauth_client_documents.py`.
