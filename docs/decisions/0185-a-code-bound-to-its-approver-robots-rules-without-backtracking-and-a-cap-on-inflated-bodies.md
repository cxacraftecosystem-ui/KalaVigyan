# 0185. An authorization code keeps its approver's token version, a robots.txt rule is matched without a regular expression, and the fetcher's byte cap holds on the inflated body

An MCP authorization code not yet exchanged now ends with the sessions of the account that
approved it, as a connection does; the fetcher matches a robots.txt rule piece by piece, so no rule
can hold its event loop; and a body a server compresses anyway is inflated no further than the
fetch's byte cap.

Date: 2026-11-24. Status: accepted (the lead's review-fix round of 2026-11-24, lane security, on
findings a reviewer reported and a second reviewer traced through the code). It amends
[decision 0101](0101-knowledge-architecture-for-every-craft.md) (item 15, Authentication: when a
code ends) and [decision 0007](0007-web-search-and-fetcher.md) (the sandbox's robots.txt and size
caps). The contracts are `docs/contracts/mcp-oauth.md` (Tokens and Storage) and
`docs/contracts/research.md` (the fetcher service).

| For | Read |
|---|---|
| The MCP sign-in whose codes this ends | [decision 0101](0101-knowledge-architecture-for-every-craft.md), item 15 |
| The fetcher sandbox, its robots.txt and its caps | [decision 0007](0007-web-search-and-fetcher.md) |
| Why the new column has a server default | [decision 0151](0151-a-release-the-live-side-can-read.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **A code outlived the change that ended its sessions.** `oauth_tokens._exchange_code` checked a
  code with `sessions_live_since(user, code.createdAt)`, which built its claims from the account's
  current `tokenVersion`, compared that version with itself, and so noticed only
  `sessionsValidFrom` and `deletedAt`. A password change, a two-step change, a role change and an
  admin asking for a new password move only `tokenVersion`, so a code approved before any of them
  still exchanged, and the connection it made stored the moved version and lived on, refreshed for
  30 days at a time. Anyone holding a stolen session could approve a fresh code every few minutes
  and exchange the newest one after the victim changed their password, although `mcp-oauth.md`
  promised that a password change ends every connection.
- **A robots.txt rule could hang the fetcher.** `RobotsRule.of` turned every `*` into `.*` for
  Python's backtracking `re`. The rule `/*a*a…*a*!` with sixteen `a`s, against a path of 2,000
  `a`s (a URL may have 2,048 characters), backtracks through about C(2000, 16) placements. The
  check runs on every hop, synchronously on kv-fetcher's one event loop, where no
  `asyncio.timeout` can interrupt it, so every fetch and `/health` would hang while systemd saw a
  live process and never restarted it.
- **The byte cap counted inflated bytes too late.** Every hop asks for `Accept-Encoding: identity`,
  but httpx inflates whatever `Content-Encoding` a server sends, one raw read at a time (a TLS
  record, up to 16 KiB) with no bound on the output, and `transport._read` compared the cap only
  after appending. A 16 KiB record of gzipped zeros inflates to about 16.9 MB before the 5 KB
  client-document cap or the 3 MiB page cap was looked at, about 34 MB at a fetch's peak, against
  kv-fetcher's `MemoryMax` of 768 MB shared by its sixteen fetch slots.

## Decision

1. **A code carries its approver's token version.** `OAuthCode.userTokenVersion` (migration
   `0101_oauth_code_token_version`, `INTEGER NOT NULL DEFAULT 0`) is written by
   `oauth_consent.approve` from the account, which the approve route has just matched to the
   session's token. The exchange holds the code to the rule a connection is held to,
   `oauth_tokens.grant_matches_user`, which now takes a code or a connection (in RFC 6749 an
   authorization code is an authorization grant): a moved token version, sessions ended after the
   code was made, or a deleted account is `invalid_grant`, and the connection keeps the code's
   version. `sessions_live_since` is gone. The server default serves a code the release before
   stores while the new colour starts: such a code exchanges only for an account still at version
   0, which no change has moved, and any other is refused, so its client signs in again. Rejected:
   deleting an account's unexchanged codes in each place that moves `tokenVersion` (fifteen
   today, and the next one would forget), and a null default read under the old check (a second
   rule kept for good).
2. **A robots.txt rule is matched piece by piece.** `RobotsRule` keeps the canonical literal pieces
   between its `*`s and whether `$` ends it, in place of a compiled expression. The path must start
   with the first piece; each later piece is found leftmost after the one before (`str.find`);
   under `$` the last piece must end the path without overlapping what came before, and without
   `$` it need only be found. For patterns of `*` alone, leftmost first is exact, so every verdict
   of the RFC's examples and of the earlier tests stands, and a rule costs at most a scan of the
   path for each of its pieces. Rejected: a regular expression under a time limit (the matching
   runs in C and holds the loop) and matching in the parser processes (a process round trip on
   every hop for what one scan decides).
3. **The cap holds on the inflated body.** `fetcher/content_codings` reads a body sent `gzip`,
   `x-gzip` (which RFC 9110 reads as gzip) or `deflate` (zlib, or the raw stream some servers
   send) from httpx's raw stream, with zlib's `max_length` set to what is left of `maxBytes` plus
   one byte, so no step holds more decoded bytes than the cap allows and the cap check refuses the
   byte past it as `TOO_LARGE`. Any other coding, or a chain of two or more, is `CONTENT_TYPE`
   before the body is read; a body without a coding is read as before, and one that does not
   inflate is the `ExternalFailure` httpx's decoding error was. Rejected: refusing every coded
   body, which the finding also offered, since a host that ignores `identity` would lose its pages
   and its robots.txt would disallow the whole host.

## Consequences

- No connection can be made from a code approved before a password, two-step or role change or an
  admin's request for a new password, so the end of every connection that `mcp-oauth.md` promises
  holds from approval to exchange. A code in flight across a release is refused only for an
  account above version 0, whose client starts the sign-in again.
- The migration follows `0100_signed_in_chunks_public`; the deploy's `alembic upgrade head` applies
  it, and the release before reads and writes `OAuthCode` unchanged.
- A hostile robots.txt costs at most a scan of the path for each piece of each rule, within the
  512 KiB file cap, and can no longer hold the fetcher's loop.
- A gzip or deflate bomb costs at most `maxBytes` plus one decoded byte and one raw read. A `br` or
  `zstd` body, which production could not decode before either (`brotli` is a development
  dependency only), is refused as `CONTENT_TYPE` instead of being read as compressed bytes, and a
  robots.txt sent so disallows its host, as an unreadable file does.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/db/test_oauth_db.py`,
`backend/tests/mcp/test_oauth_sessions.py`, `backend/tests/test_oauth_code_token_version_migration.py`,
`backend/tests/fetcher/test_robots_rfc.py` and `backend/tests/fetcher/test_content_codings.py`.
