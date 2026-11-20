"use client";

import { useAuth } from "@/components/AuthProvider";
import { ClientSteps } from "@/components/connect/ClientSteps";
import { CopyCode } from "@/components/connect/CopyCode";
import { FirstSession } from "@/components/connect/FirstSession";
import { GuideSection } from "@/components/connect/GuideSection";
import { SignInSteps } from "@/components/connect/SignInSteps";
import { ToolCatalogue } from "@/components/connect/ToolCatalogue";
import { useConnectFacts, type ConnectFactsView } from "@/components/connect/useConnectFacts";
import { FactGrid, type Fact } from "@/components/editorial/FactGrid";
import { PageHeader } from "@/components/PageHeader";
import { RetryPanel } from "@/components/RemotePanels";
import { clientGuides, CONNECT_TITLE } from "@/lib/connectClients";
import { abilitySentence, firstSession, heldScopes, SCOPE_GUIDES } from "@/lib/connectRoles";
import { countNoun, listText } from "@/lib/format";
import type { McpScope } from "@/lib/oauthContract";
import { roleLabel } from "@/lib/permissions";
import type { User } from "@/lib/types";

export const CONNECT_LEDE = "Give your AI assistant KalaVigyan's own tools. It reads crafts with their quotes and sources without signing in; once you sign in it asks, and contributes where your role allows, in your name.";
export const READ_FAILED = "The server could not be read just now. Try again in a moment.";

export function scopeWords(held: readonly McpScope[]): string {
  return listText(SCOPE_GUIDES.filter((guide) => held.includes(guide.scope)).map((guide) => guide.title.toLowerCase()));
}

export function glanceFacts(facts: ConnectFactsView, user: User | null): Fact[] {
  const glance: Fact[] = [];
  if (facts.address) glance.push({ label: "The address", value: <span className="font-code text-label [overflow-wrap:anywhere]">{facts.address}</span> });
  if (user) glance.push({ label: "Your account", value: `${roleLabel(user.role)}: ${scopeWords(heldScopes(user))}` });
  glance.push({ label: "Signing in", value: "Your roster account, through OAuth 2.1 with PKCE" });
  if (facts.catalogue) glance.push({ label: "On the server now", value: `${countNoun(facts.catalogue.tools.length, "tool")} and ${countNoun(facts.catalogue.prompts.length, "guided prompt")}` });
  return glance;
}

export function ConnectGuide({ initial }: { initial: ConnectFactsView }) {
  const { user } = useAuth();
  const { address, catalogue, failed, retry } = useConnectFacts(initial);
  const held: McpScope[] = user ? heldScopes(user) : ["read"];
  const missing = !address || !catalogue;
  return (
    <div className="grid min-w-0 gap-14" data-testid="connect-guide">
      <div className="grid gap-8">
        <PageHeader kicker="MCP server" title={CONNECT_TITLE} description={CONNECT_LEDE} back={false} />
        <FactGrid facts={glanceFacts({ address, catalogue }, user)} columns={4} />
        {missing && failed ? <RetryPanel message={READ_FAILED} onRetry={retry} /> : null}
      </div>
      <GuideSection id="address" title="The address" about="One address for every client below; paste it wherever your AI asks for an MCP server's URL." ready={Boolean(address)} failed={failed}>
        {() => <div className="max-w-measure">{address ? <CopyCode code={address} kind="address" large /> : null}</div>}
      </GuideSection>
      <GuideSection id="clients" title="Add it to your AI" about="Each client's own steps, as its documentation gives them, with the address filled in." ready={Boolean(address)} failed={failed}>
        {() => <ClientSteps guides={clientGuides(address ?? "")} />}
      </GuideSection>
      <GuideSection id="sign-in" title="What signing in does" about="Reading needs no sign-in. The first time your AI needs more, it signs you in." ready>
        {() => <SignInSteps held={held} ability={user ? abilitySentence(user) : null} />}
      </GuideSection>
      <GuideSection id="tools" title="What your AI can do" about="The server's own list of tools and guided prompts, grouped by the work they do; a tool the server adds appears here by itself." ready={Boolean(catalogue)} failed={failed}>
        {() => (catalogue ? <ToolCatalogue catalogue={catalogue} /> : null)}
      </GuideSection>
      <GuideSection id="first-session" title="A first session" about="Things to ask your AI once it is connected, each using a tool or prompt the server offers you." ready={Boolean(catalogue)} failed={failed}>
        {() => (catalogue ? <FirstSession suggestions={firstSession(catalogue, held)} contributes={held.includes("contribute")} /> : null)}
      </GuideSection>
    </div>
  );
}
