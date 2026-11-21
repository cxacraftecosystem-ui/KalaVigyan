import { STEP_LIST } from "@/components/connect/ClientSteps";
import { SCOPE_GUIDES } from "@/lib/connectRoles";
import type { McpScope } from "@/lib/oauthContract";

export const SIGN_IN_STEPS = [
  "Your AI opens KalaVigyan's sign-in page in your browser.",
  "You sign in with the account the access roster admitted, with two-step verification where your role needs it.",
  "You read and accept the MCP terms of use, once for each version of them.",
  "You approve the scopes: read is always given, and a scope your role cannot hold is shown with what it needs.",
  "KalaVigyan returns you to your AI, which stays signed in while you use it at least once a month; a password change or Sign out everywhere ends the connection."
] as const;

export const HELD_WORDS = { yes: "Yours", no: "Not yours" } as const;

const ROW = "grid min-w-0 gap-x-6 gap-y-1 border-b border-rule py-3 md:grid-cols-[7rem_minmax(0,1fr)_11rem_6rem]";

function ScopeTable({ held }: { held: readonly McpScope[] }) {
  return (
    <div role="table" aria-label="Scopes" className="grid border-t border-ink-1" data-testid="scope-table">
      <div role="row" className={`${ROW} max-md:sr-only`}>
        {["Scope", "What it lets your AI do", "Who may give it", "Your account"].map((label) => (
          <span key={label} role="columnheader" className="font-ui text-label text-ink-3">
            {label}
          </span>
        ))}
      </div>
      {SCOPE_GUIDES.map((guide) => (
        <div key={guide.scope} role="row" className={ROW} data-testid={`scope-${guide.scope}`}>
          <span role="rowheader" className="font-ui text-h4 text-ink-1">
            {guide.title}
          </span>
          <span role="cell" className="font-ui text-ui font-normal text-ink-2">
            {guide.allows}
          </span>
          <span role="cell" className="font-ui text-label text-ink-3">
            {guide.who}
          </span>
          <span role="cell" className="font-ui text-label text-ink-1">
            {held.includes(guide.scope) ? HELD_WORDS.yes : HELD_WORDS.no}
          </span>
        </div>
      ))}
    </div>
  );
}

export function SignInSteps({ held, ability }: { held: readonly McpScope[] | null; ability: string | null }) {
  return (
    <div className="grid min-w-0 gap-8">
      <div className="grid min-w-0 gap-8 lg:grid-cols-2 lg:gap-x-12">
        <ol className={STEP_LIST}>
          {SIGN_IN_STEPS.map((step) => (
            <li key={step} className="ps-1 text-ink-1">
              {step}
            </li>
          ))}
        </ol>
        {ability ? (
          <p className="m-0 font-reading text-lede text-ink-1" data-testid="connect-ability">
            {ability}
          </p>
        ) : null}
      </div>
      <ScopeTable held={held ?? ["read"]} />
    </div>
  );
}
