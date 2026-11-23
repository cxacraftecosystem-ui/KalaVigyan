import { listText } from "@/lib/format";
import type { McpCatalogue } from "@/lib/connectCatalogue";
import { MCP_SCOPES, type McpScope } from "@/lib/oauthContract";
import { hasRank, roleLabel } from "@/lib/permissions";
import type { User } from "@/lib/types";

export const ASK_CAPABILITY = "ASK_STANDARD";
export const CONTRIBUTE_CAPABILITY = "PROPOSE_KNOWLEDGE";
export const OWN_PROPOSALS_PATH = "/contributions/facts";
export const CONNECTED_APPS_PATH = "/settings?tab=security";

export type ScopeGuide = { scope: McpScope; title: string; allows: string; who: string };

export const SCOPE_GUIDES: readonly ScopeGuide[] = [
  { scope: "read", title: "Read", allows: "Read crafts, facts with their quotes and sources, sections, layouts and components, as anyone signed out reads them.", who: "Everyone" },
  { scope: "ask", title: "Ask", allows: "Ask questions and receive cited answers in your name; each counts against your asks, as on the site.", who: "Every role" },
  { scope: "contribute", title: "Contribute", allows: "Propose facts, sources, structure, components, pages and pictures in your name, and claim open work; each proposal passes the same checks as one made on the site.", who: "Researcher, Professor, Admin and Master Admin" },
  { scope: "review", title: "Review", allows: "Read the review queue and admin reports, stage decisions that a person confirms on the Review page, and refresh changed pages; nothing staged is published until it is confirmed.", who: "Admin and Master Admin, with two-step verification on, signed in within 15 minutes" }
];

const VERBS: Record<McpScope, string> = { read: "read", ask: "ask", contribute: "contribute", review: "review" };

export function heldScopes(user: User): McpScope[] {
  const capabilities = new Set(user.capabilities ?? []);
  const held: Record<McpScope, boolean> = {
    read: true,
    ask: capabilities.has(ASK_CAPABILITY),
    contribute: capabilities.has(CONTRIBUTE_CAPABILITY),
    review: hasRank(user, "ADMIN")
  };
  return MCP_SCOPES.filter((scope) => held[scope]);
}

export function abilitySentence(user: User): string {
  const held = heldScopes(user);
  const role = roleLabel(user.role);
  const verbs = listText(held.map((scope) => VERBS[scope]));
  const next = hasRank(user, "RESEARCHER") ? "" : " Contributing needs a Researcher account or above.";
  return `Your ${role} account lets your AI ${verbs} in your name.${next}`;
}

export type Suggestion = { key: string; ask: string; needs: { kind: "tool" | "prompt"; name: string }; scope: McpScope };

export const SUGGESTIONS: readonly Suggestion[] = [
  { key: "curate", ask: "Run the curate_page prompt for Kutch Ajrakh and show me the draft before anything is submitted.", needs: { kind: "prompt", name: "curate_page" }, scope: "contribute" },
  { key: "work", ask: "List the open work in the chemistry field, highest priority first, and claim the first task.", needs: { kind: "tool", name: "list_open_work" }, scope: "contribute" },
  { key: "quote", ask: "Check this quote against its source with read_source before you propose the fact.", needs: { kind: "tool", name: "read_source" }, scope: "contribute" },
  { key: "preview", ask: "Preview the page bundle with preview_page and give me its private link.", needs: { kind: "tool", name: "preview_page" }, scope: "contribute" },
  { key: "find", ask: "Find the crafts that use indigo and read Kutch Ajrakh's chemistry facts with their quotes.", needs: { kind: "tool", name: "find_crafts" }, scope: "read" },
  { key: "ask", ask: "Ask KalaVigyan why alum fixes madder dye on cotton, and keep the citations.", needs: { kind: "tool", name: "ask" }, scope: "ask" },
  { key: "coverage", ask: "Show which of the sixteen fields Kutch Ajrakh covers, and which are thin or missing.", needs: { kind: "tool", name: "get_page" }, scope: "read" }
];

export const FIRST_SESSION_SIZE = 4;

function offered(catalogue: McpCatalogue, needs: Suggestion["needs"]): boolean {
  const names = needs.kind === "tool" ? catalogue.tools.map((tool) => tool.name) : catalogue.prompts.map((prompt) => prompt.name);
  return names.includes(needs.name);
}

export function firstSession(catalogue: McpCatalogue, held: readonly McpScope[]): Suggestion[] {
  return SUGGESTIONS.filter((suggestion) => held.includes(suggestion.scope) && offered(catalogue, suggestion.needs)).slice(0, FIRST_SESSION_SIZE);
}
