import { STEP_LIST } from "@/components/connect/ClientSteps";
import { CopyCode } from "@/components/connect/CopyCode";
import { TextLink } from "@/components/ui/TextLink";
import { CONNECTED_APPS_PATH, OWN_PROPOSALS_PATH, type Suggestion } from "@/lib/connectRoles";

export const FOLLOW_PATHS = [
  { href: OWN_PROPOSALS_PATH, label: "Your facts" },
  { href: "/contributions/components", label: "Your components" },
  { href: "/contributions/pictures", label: "Your pictures" }
] as const;

function FollowAndRevoke({ contributes }: { contributes: boolean }) {
  return (
    <dl className="m-0 grid min-w-0 content-start border-t border-ink-1">
      {contributes ? (
        <div className="grid gap-1 border-b border-rule py-3" data-testid="follow-proposals">
          <dt className="font-ui text-h4 text-ink-1">Follow what you submitted</dt>
          <dd className="m-0 grid gap-2 font-ui text-ui font-normal text-ink-2">
            <span>What your AI proposes is listed with what you propose on the site, with each check&apos;s reasons and the reviewers&apos; word; your AI reads the same through my_tasks and get_proposal.</span>
            <span className="flex flex-wrap gap-x-5 gap-y-1">
              {FOLLOW_PATHS.map((path) => (
                <TextLink key={path.href} href={path.href} standalone>
                  {path.label}
                </TextLink>
              ))}
            </span>
          </dd>
        </div>
      ) : null}
      <div className="grid gap-1 border-b border-rule py-3" data-testid="revoke-connection">
        <dt className="font-ui text-h4 text-ink-1">Revoke a connection</dt>
        <dd className="m-0 grid gap-2 font-ui text-ui font-normal text-ink-2">
          <span>Connected apps in Settings lists each app with what it may do and when it was last used; Revoke ends its access at once.</span>
          <span>
            <TextLink href={CONNECTED_APPS_PATH} standalone>
              Open connected apps
            </TextLink>
          </span>
        </dd>
      </div>
    </dl>
  );
}

export function FirstSession({ suggestions, contributes }: { suggestions: readonly Suggestion[]; contributes: boolean }) {
  return (
    <div className="grid min-w-0 gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-x-12">
      <ol className={STEP_LIST} data-testid="first-session">
        {suggestions.map((suggestion) => (
          <li key={suggestion.key} className="min-w-0 ps-1">
            <CopyCode code={suggestion.ask} kind="request" />
          </li>
        ))}
      </ol>
      <FollowAndRevoke contributes={contributes} />
    </div>
  );
}
