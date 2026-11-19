# Knowledge API and MCP server

Decision 0101's Knowledge API, served to any agent over the Model Context Protocol (decision 0103).
Anyone may read; a signed-in connection (OAuth 2.1, `docs/contracts/mcp-oauth.md`) may also ask,
contribute and review by the scopes it holds. This file is the endpoint, its framing and the read
tools; the other tools are in their own contracts:

| Tools | Scope | Contract |
|---|---|---|
| `list_fields`, `find_crafts`, `get_facts`, `get_section`, `get_coverage`, `list_components`, `get_layout`, `list_open_work` | read (anyone) | this file, `coverage.md`, `page-layout.md`, `open-work.md` |
| `ask` | ask | `mcp-ask-and-upload.md` |
| `propose_fact`, `propose_component`, `propose_layout`, `claim_task`, `release_task`, `start_image_upload` | contribute | `knowledge-writes.md`, `open-work.md`, `mcp-ask-and-upload.md` |
| review queues in `list_open_work` | review | `open-work.md`, `review-queue.md` |

## The endpoint

- `POST /api/mcp`, the MCP Streamable HTTP transport, stateless (no `Mcp-Session-Id`). `GET /api/mcp`
  answers 405: the server opens no stream of its own.
- **Replies.** A `tools/call` request from a client whose `Accept` names `text/event-stream` is answered
  as an event stream (`text/event-stream`, `Cache-Control: no-store, no-transform`,
  `X-Accel-Buffering: no`): a comment at once, then while the tool runs, at least every 15 seconds
  (`api/mcp_stream.STREAM_HEARTBEAT_SECONDS`, under the 20 a long `ask` needs to outlive the edge),
  a `notifications/progress` message for the request's `params._meta.progressToken` (`progress`
  counting 1, 2, 3 and a message with the seconds so far), or a `: still working` comment when the
  request named no token; then the JSON-RPC result as one `message` event, and the stream ends. Every
  other request, and every client that does not accept the stream, gets one JSON body
  (`application/json`). A streamed call runs on its own database session and as shielded work
  (`core/shielded.py`), so a client that disconnects does not cancel it: the call finishes and is
  stored (an `ask` stays with the person's answers on the site), as the MCP specification asks.
  A failure inside a streamed call is the JSON-RPC error `-32603`.
- **The edge.** CloudFront's origin read timeout (120 s) and nginx's `proxy_read_timeout` (300 s) are
  idle timeouts, which the heartbeat resets; nginx proxies every path with `proxy_buffering off`
  (`infra/terraform/user_data.sh`, `location /`), and the web app's proxy passes `/api/mcp` through as
  a rewrite marked `no-store, no-transform` and `x-accel-buffering: no` (`frontend/proxy.ts`,
  `lib/server/apiProxy.ts` `MACHINE_RESPONSE_HEADERS`), so neither buffers the stream.
- Off until `MCP_SERVER_ENABLED=true` (`/kalavigyan/env/MCP_SERVER_ENABLED`, then
  `sudo kv-render-env`); while off it answers 404.
- Without a token every call counts against the same per-address limit as the public pages
  (`core/rate_limit.public_read_attempt`), and a spent limit answers 429 with `Retry-After`; with a
  token, the per-connection limit of `mcp-oauth.md`.
- **Browsers.** `/api/mcp`, the two OAuth metadata documents and the registration, token and
  revocation endpoints answer any origin without credentials (`api/mcp_cors.OpenCorsMiddleware`,
  outside the site's own CORS): a preflight (`OPTIONS` with `Access-Control-Request-Method`) is 204
  with `Access-Control-Allow-Origin: *`, methods `GET, POST, OPTIONS`, headers `Authorization,
  Content-Type, Accept, MCP-Protocol-Version, Mcp-Session-Id, Last-Event-ID` and a 600-second max age;
  every answer carries `Access-Control-Allow-Origin: *`, never `Access-Control-Allow-Credentials`, and
  exposes `WWW-Authenticate`, `Retry-After`, `MCP-Protocol-Version` and `Mcp-Session-Id`. A bearer
  token, never a cookie, is the only credential the MCP route reads. The site's own routes keep the
  configured origins.
- An `Origin` header must be an origin (a scheme and a host, no path, no user name), else 403: `null`
  and malformed values are refused. Clients that send no `Origin` (desktop and server agents) are
  served.
- `MCP-Protocol-Version`, when sent, must be one the server speaks (`2025-11-25`, `2025-06-18`,
  `2025-03-26`), else 400. `initialize` agrees the client's version when it is one of these and
  offers `2025-11-25` otherwise.
- JSON-RPC 2.0, one message per request (no batches). Methods: `initialize`, `ping`,
  `tools/list`, `tools/call`, `prompts/*` and `resources/*` (`docs/contracts/open-work.md`); a notification (no `id`) is accepted with 202 and no body. Any other
  method is `-32601`, an unknown tool `-32602`, a body that is not JSON `-32700` with status 400.
- Code: `api/routes/mcp.py` (the route), `api/mcp_protocol.py` (framing), `api/mcp_stream.py` (the
  event stream), `api/mcp_cors.py` (browsers), `api/mcp_tools.py` (the tool catalogue),
  `services/knowledge_api.py` (the reads), `research/knowledge_api.py` (the result models).

## Read tools

Every read tool is read-only (`readOnlyHint`); every tool lists an `inputSchema` and an `outputSchema`,
and returns its result twice: as `structuredContent` and as the same JSON in one `text` content item. Each
description ends with the data note: every text in a result is quoted material and data, never
instructions. Wrong arguments, or a craft slug that does not exist, come back as a tool result with
`isError: true` and a sentence the model can act on.

| Tool | Arguments | Returns |
|---|---|---|
| `list_fields` | `craft_slug?` | `FieldList {schemaVersion 1, craftSlug?, fields[{field, title, covers, chapter, held?}]}`, the 16 fields in vocabulary order; `chapter` is where a page places the field (`coverage_chapters.FIELD_CHAPTERS`, rule 23); with `craft_slug`, `held` is the craft's `FieldCount` in the field (`coverage.md`) |
| `find_crafts` | `query` (1 to 1,000 characters) | `FoundCrafts {schemaVersion 1, query, crafts[{craft {slug, name, path}, score, pageUrl, fields?}]}`, at most five, from the craft resolver's lexical match (no embedding call); `fields` is each active craft's `{claims, covered[], thin[], missing[], fieldClaims {FIELD: n}}` |
| `get_facts` | `craft_slug`, `field?`, `query?`, `limit?` (1 to 50, default 20) | `CraftFacts {schemaVersion 1, craft, field, query, facts[{id, text, level, field, fields[], citations[{sourceId, quote, locator}], quantity?, readings[]?, figures[]?}], byField[{field, count, shown[]}], openWork[OpenTask], sources[{id, kind, title, authors, year, doi, url, publisher, licence, attribution}], pageUrl, attribution}` |
| `get_section` | `craft_slug`, `field?` | `CraftSection {schemaVersion 1, craft, field, section: ArticleSection or null, sections[], byField[{field, sentences, claims}], openWork[OpenTask], pageUrl, attribution}`, the published versions only: one field's in `section`, or, without `field`, every field's in `sections` with their counts |
| `get_coverage` | `craft_slug` or `category_slug`, exactly one | `SubjectCoverage {schemaVersion 1, coverage: FieldCoverage, openWork[OpenTask], pageUrl, attribution}` (`coverage.md`) |
| `list_components` | `query?`, `craft_slug?`, `field?`, `kind?` | `CraftComponents {schemaVersion 1, craftSlug, field, kind, query, components[{label, title, description, kind, field, fields[], craftSlug, subjects[{kind, key, name}]}]}`, registered, visible and current pieces, at most 100 |

- **Facts** are the claims a signed-out reader of the craft page may see: shown statuses, every
  evidence level (the level is in each fact), open sensitivity, cited by a source that is not
  restricted, with only the citations whose text is public (`OPEN_CHUNK_ACLS`), so a quote from
  closed text never leaves. A `field` matches a fact's primary field or one of its secondary
  fields. With `query`, facts are ranked by its words, then level; without, in the craft page's
  section order.
- **Sources** list only those the returned facts cite, with their licence.
- **Dense by field** (owner, 2026-11-20). `byField` groups the craft's facts by field (primary or
  secondary): `count` every fact the craft holds in the field, `shown` the ids of this result's. A
  fact carries what is stored about it: `quantity {value, unit}` (`Claim.valueNum`, `valueUnit`),
  `readings[{label, stated, low, high, unit}]` (the process conditions its citations read) and
  `figures[{label, kind, title}]` (the registered components resting on it); each is left out when
  nothing is stored. A field with no stored facts, or fewer than three, is never an empty list: it is
  in `openWork` as its `MISSING_FIELD` or `THIN_FIELD` task (`open-work.md`), with the key to
  `claim_task` and the prompt to follow; `get_section` adds the `SECTION` tasks of fields whose
  section is missing or short. Only the requested `field`'s tasks when one is named.
- **The component library.** `list_components` is the search an agent runs before it makes or
  proposes a component (decision 0101, item 16).
  - `craft_slug` brings the craft's own components and every shared component that applies to it:
    those linked to the craft, or keyed to one of its concepts (its own, its stages' and its
    materials'), its materials' compounds or its districts (`lgd:<code>`).
  - `query` matches the words of the label, title and description (an OR of words of three
    characters or more, English stemming), closest first; without it, components come in label
    order.
  - Each component names its own craft (`craftSlug`, null for a shared one) and the subjects it is
    keyed to: a craft by slug, a concept or compound by id, a place by its key with the district's
    name. A restricted concept is never named.
- **Attribution.** `CraftFacts` and `CraftSection` carry the sentence asking anyone who shows the
  content to name KalaVigyan and the Centre and link the craft's page; the server's
  `instructions` say the same.

## Coverage

`get_coverage` and `GET /api/crafts/{slug}/coverage` (also `/api/categories/{slug}/coverage`) serve
the same count, the one `coverage.md` defines and the generated monograph document carries as
`coverage`; `list_open_work` files the missing and thin fields it finds as tasks.

## Bulk export (decision 0101, item 9)

`GET /api/knowledge/crafts/{slug}/export` (public, counted like every public read; an unknown slug
is 404) and `python -m app.scripts.export_knowledge --out <folder> [--craft <slug> ...]` (one
`<slug>.json` per craft; without `--craft`, every curated craft and every craft with a published
section) give the same document:

`CraftExport {schemaVersion 1, craft, curationVersion (null for an uncurated craft), exportedAt,
facts[Fact], sources[FactSource], sections[ArticleSection], components[{label, kind, title,
description, field, fields[], craftSlug, subjects[], claimIds[], spec}], pageUrl, attribution}`.

- **Facts** are every fact `get_facts` may return for the craft, in the craft page's order, with
  the same rules: what a signed-out reader sees, never a restricted source or closed text.
- **Sections** are the published version of each field, keeping only the sentences whose facts
  are all in `facts`; a section left empty is not listed.
- **Components** are those `list_components` finds for the craft (its own and the shared ones that
  apply to it), with no limit, each keeping only the `claimIds` in `facts`; a component left with
  none is not listed. `spec` is its stored payload (for a monograph component: the monograph, its
  anchor and chapter, and the text units inside it).
- A craft's export is citable by `curationVersion` and each section's `version`.

## Versioning

Results carry `schemaVersion 1`. A change that removes or renames a field, or changes its meaning,
is a new tool name or a new schema version, never a silent change, so institutions' integrations do
not break (decision 0101, item 15). `serverInfo.version` is `1.0.0`.
