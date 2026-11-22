# 0150. Each MCP call keeps its client and its reason for 180 days and its count for good, and the box ships its logs to CloudWatch

A tool call over MCP now records the client that made it and, when it failed, the refusal's own
words with every argument withheld; the calls are kept 180 days and counted by day, client, tool and
outcome for good, and a Master Admin reads them on an MCP activity screen. The box's services and
nginx ship their logs to CloudWatch Logs, one group per service, kept 30 days, with no secret,
statement parameter, capability token or body in any shipped line.

Date: 2026-11-23. Status: accepted (the lead's debt-clearing brief, lane MCP activity and logs, from
the owner's question of 2026-11-22, "How are we maintaining the MCP logs and all?", after the
Sanganeri contribution through Claude). The contracts are `docs/contracts/mcp-oauth.md` (Guards, MCP
activity, Storage), `docs/contracts/nightly-upkeep.md` (3d) and `docs/contracts/infra.md` (Logs);
the operator's side is `docs/RUNBOOK.md`, Logs.

| For | Read |
|---|---|
| Sign-in and the tool-call audit this extends | [mcp-oauth.md](../contracts/mcp-oauth.md) and [decision 0101](0101-knowledge-architecture-for-every-craft.md), item 15 |
| The nightly bounds a new step follows | [nightly-upkeep.md](../contracts/nightly-upkeep.md) |
| The box, its units and the deploy | [RUNBOOK.md](../RUNBOOK.md) and [infra.md](../contracts/infra.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- `McpToolCall` held the connection, token, tool, outcome and time of every call. Nothing read it,
  nothing pruned it, and a failed call kept no reason, so a contributor's "it failed" could not be
  answered from the record. A call the server failed while answering (an exception in a tool) was
  not recorded at all.
- The API, the worker, the fetcher and the contribution worker log JSON lines to journald on the one
  box, capped at 500 MB, and nginx writes its own files. Nothing left the box: a replaced box lost
  them, and nobody could search them without a shell.
- The request line logged the raw path, so the capability token of a shared answer or lesson, a page
  preview, an upload link or an upload slot was in the journal; a database error's text carried its
  statement's parameters and Postgres's `DETAIL` line with the refused row's values.

## Decision

1. **The reason is the refusal's own message, made safe.** `api/mcp_auth.call_reason` reads a tool
   error's text, a protocol error's message, or names a notification that got no reply; a call the
   server failed is rolled back and recorded as `PROTOCOL_ERROR` with the message the client gets
   (`record_failed_call`), and the failure then goes on unchanged. `research/mcp_activity.failure_reason`
   replaces every string the call sent as an argument, and the name of a tool that does not exist,
   by `…`; masks email addresses, phone and Aadhaar-like numbers with the one set of personal-data
   patterns; masks key and token shapes with `redact_secrets`; and cuts the text to 300 characters.
   Withholding what was sent, rather than trusting each refusal not to echo it, keeps "never the
   arguments" true for refusals written later. A succeeded call keeps no reason, which a check on
   the table holds; the store refuses a reason that breaks either rule.
2. **The client is the client's name.** `McpCaller.client_name` is the connection's
   `OAuthClient.name`, stored on each call (`clientName`, filled from each connection by migration
   `0074_mcp_activity`). Counting by name groups a client's many registrations ("Claude" registers
   anew) and keeps the count meaningful after a registration or an account is deleted.
3. **180 days of calls, counts for good.** The nightly step `mcp_activity_upkeep.keep_mcp_activity`
   (3d) counts each finished India day whole, at most 31 days a night, into `McpToolCallDay` (day,
   client name, tool, outcome, calls; no connection and no account), and then deletes at most 20,000
   calls a night that are older than 180 days and whose day is counted, so no call is pruned before
   it is counted. A count is never recomputed from a pruned day.
4. **One Master Admin screen.** `GET /api/settings/mcp-activity` answers one contract
   (`shared/mcp.activity.golden.json`): for 7, 30 or 180 days, optionally one client or one
   connection, the calls by outcome over time (by day, or by week for 180 days), by tool, by client
   and by connection, the newest 50 failures with their reasons, and each connection's and client's
   last use. By client it reads the counts for counted days and the calls of the rest; by connection
   it reads the calls. `/admin/mcp` draws it with the system's figure, tables and status badges, and
   keeps its period and scope in its address.
5. **CloudWatch Logs through the box's own syslog.** The agent cannot read journald, so each unit
   names itself (`SyslogIdentifier`), journald forwards to rsyslog, rsyslog writes one file per
   service under `/var/log/kalavigyan/`, and the CloudWatch agent, pinned by version and SHA-256 in
   `infra/deploy/cloudwatch-agent.pin` (1.300075.0b2061, signature checked against AWS's key when it
   was pinned), ships those files and nginx's to six groups made by Terraform (`infra/terraform/logs.tf`,
   30 days), the box role allowed to write only them. The journal is kept as it was. A new box
   installs rsyslog and the agent from `user_data.sh`; every release, the first included, installs
   the files of `infra/deploy/logs/` (`ship_logs.sh`), so there is one copy of the configuration and
   a running box gets it with its next deploy. A release whose log step fails warns and goes on:
   shipping logs is not a reason to hold back a fix.
6. **Nothing secret is shipped, filtered at the source.** The request line masks every `{token}`
   path value (`core/logging.logged_path`); `redact_secrets` also masks KalaVigyan's own `kvmcp_`
   and `kv1_` tokens and Postgres `DETAIL` lines; the engine hides statement parameters
   (`hide_parameters`). nginx's shipped line is its own JSON format with the path from a map that
   masks the same capability routes, and no query string, address, referrer, cookie, header or body;
   the agent drops an nginx error line that names one of those routes. A test derives the routes from
   the app, so a new capability route fails until both maps cover it.

## Consequences

- Migration `0074_mcp_activity` adds two columns and a table; its parent is the round's chain head
  when the lane merges.
- The daily counts stay small: one row per day, client, tool and outcome.
- A connection's own history ends at 180 days; older history is by client only.
- An error's text in the logs no longer shows the values of the row Postgres refused; the
  constraint's name and the statement remain, and the values are found in the database.
- The lead applies the Terraform (six log groups and one inline policy); until then the agent logs
  that the groups are missing and the app runs as before.
- Logs cost about US$0.67 per GB ingested in ap-south-1, a few dollars a month at today's volume.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/mcp/test_mcp_activity_reason.py`, `backend/tests/mcp/test_mcp_activity_route.py`,
`backend/tests/db/test_mcp_activity_db.py`, `backend/tests/test_log_redaction.py`,
`backend/tests/test_log_shipping.py`, `backend/tests/db/test_log_safety_db.py` and
`frontend/e2e/mcp-activity-unit.spec.ts`.
