import { FormAlert } from "@/components/auth/FormAlert";
import { FactGrid } from "@/components/editorial/FactGrid";
import { deviceCaution, identityFacts, returnsToThisDevice } from "@/lib/oauthConsent";
import type { AuthorizationPrompt } from "@/lib/oauthContract";

export function ClientIdentity({ prompt }: { prompt: AuthorizationPrompt }) {
  return (
    <section className="grid gap-3" aria-labelledby="client-h" data-testid="client-identity">
      <h2 id="client-h" className="text-h3 font-reading text-ink-1">
        Who is asking
      </h2>
      <FactGrid facts={identityFacts(prompt)} columns={2} />
      {returnsToThisDevice(prompt) ? (
        <FormAlert tone="warning" testId="device-caution">
          {deviceCaution(prompt)}
        </FormAlert>
      ) : null}
    </section>
  );
}
