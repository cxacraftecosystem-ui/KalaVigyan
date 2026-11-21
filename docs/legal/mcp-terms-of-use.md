# MCP terms of use (version 2026-11-19)

Approved by the owner on 2026-11-19. These are the terms a person accepts when they connect an AI
agent to KalaVigyan through the MCP server (decision 0101, item 15). They are versioned; a new
version is asked for again at the next sign-in.

The text has one copy: `backend/app/data/mcp_terms_of_use.md`, served at `GET /api/oauth/terms`
and shown on the consent screen. Its version is `MCP_TERMS_VERSION` in
`backend/app/research/oauth_rules.py`. Change the text there, and raise the version with it.

**How this document is kept true.** `backend/tests/mcp/test_mcp_terms_copy.py` holds this page's
heading to `MCP_TERMS_VERSION`, its pointer to the one served file, and the terms' text out of it, so
the text has one home. A change to the text is a new version, with the owner's approval.
