# 0103. The MCP server, slice 1: public read tools over our own JSON-RPC framing

The MCP server's first slice ships public read tools alone, anonymous and switched off by default,
over KalaVigyan's own JSON-RPC framing instead of the MCP SDK. Its reads are the public page's
reads, finding a craft costs nothing, and browser origins are checked.

Date: 2026-11-19. Status: accepted (built without the owner present, on the owner's instruction to
start on the MCP server and continue on Claude's recommendations).

| For | Read |
|---|---|
| What amended it | [0111 Twenty-one MCP tools in six groups, with small schemas](0111-fewer-mcp-tools.md): the tools it names; its services and contracts stand |
| What it builds on | [0101 One knowledge architecture for every craft: facts, sections, components, monographs](0101-knowledge-architecture-for-every-craft.md): slice 1 of the MCP server of items 7, 9 and 15 |
| The contracts it names | [knowledge-api.md](../contracts/knowledge-api.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0101 (items 7, 9 and 15) asks for a remote MCP server on a Knowledge API: read tools,
asking, contributing, open work, with OAuth 2.1 sign-in and terms acceptance. Asking needs a
signed-in reader and spends money; contributing needs the gates and the review queue of build
steps 4 and 5, which do not exist yet. Item 9 already makes the read tools public, and every page
except asking is readable without signing in (decision 0097).

## Decision

1. **Slice 1 ships the read tools alone, anonymous and switched off by default**:
   `list_fields`, `find_crafts`, `get_facts`, `get_section` and `list_components` at
   `POST /api/mcp`, behind `MCP_SERVER_ENABLED` (`docs/contracts/knowledge-api.md`).
2. **The reads are the public page's reads.** Facts come from `knowledge_view.claims_for` with the
   signed-out chunk rules, so a restricted source or a quote from closed text never leaves, and the
   new `Claim.field` and `Claim.fields` (decision 0102) filter them by field.
3. **Finding a craft costs nothing.** `find_crafts` uses the resolver's lexical match only; the
   semantic step would spend an embedding call per anonymous request.
4. **Our own framing, not the MCP SDK.** Stateless Streamable HTTP with JSON replies needs four
   methods (`initialize`, `ping`, `tools/list`, `tools/call`) and JSON-RPC errors, about 100 lines in
   `api/mcp_protocol.py`, all tested without a network. The SDK would add a dependency with its own
   server, session manager and lifespan inside our app for no behaviour we use. Revisit when the
   server needs server-sent events, resources or sampling.
5. **The route is a service route, not a public read.** Public reads are GETs that take the
   optional signed-in reader (the route inventory holds that rule); MCP is a POST, so it is counted
   by `counted_anonymous_read`, against the same per-address limit, without reading a session.
6. **Browser origins are checked**, as the MCP transport asks: a request with an `Origin` outside
   `BACKEND_CORS_ORIGINS` is refused, and agents that send none are served.

## What follows

- Slice 2: OAuth 2.1 with the web app as the authorization server, the MCP terms of use accepted
  and versioned per user, connected clients listed in Settings with revoke, then `ask`.
- Slice 3, after build steps 4 and 5: `propose_fact`, `propose_component`, `propose_layout`,
  `list_open_work`, `claim_task` and `release_task`, through the gates and the review switch, with
  Professors', Admins' and Master Admins' proposals approved at once (decision 0101, item 12), the
  MCP prompts and the `kalavigyan-contributor` skill.
- Turning slice 1 on is one parameter, `/kalavigyan/env/MCP_SERVER_ENABLED=true`.
- **Amended 2026-11-19:** `list_components` became the component library's search (`query`, `kind`,
  and a craft's shared components through its concepts, compounds and districts), the step an agent
  takes before it makes a component (decision 0101, item 16). The change only adds fields.

## How this record is kept true

The amendment of 2026-11-19 under What follows records what followed the slice. Beyond that it is
not edited except to mark it superseded: a later choice is a new record that names this one, and the
table above links the two both ways. The parts later records changed stay here as they were decided;
the later record is the one that holds. It records the choice as taken on 2026-11-19; what the code
does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the [contracts](../contracts/README.md).
