"use client";

import { useEffect, useRef, useState } from "react";

import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { useGoogleNonce } from "@/components/auth/useGoogleNonce";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { googleClientId } from "@/lib/googleIdentity";
import { beginSignIn, callbackErrorMessage, configuredOidcProviders, type OidcProvider } from "@/lib/oidcSignIn";
import { type ConfirmProvider, confirmPrompt, fetchFirstPasswordNonce } from "@/lib/passwordChange";
import type { ProviderProof } from "@/lib/signIn";

const GOOGLE_UNREACHABLE = "Couldn't reach Google. Check your connection and try again.";
const NO_PROVIDER_HERE = "To add a password, ask an administrator to send you a link to set one.";

type ConfirmEvents = {
  onProof: (proof: ProviderProof) => void;
  onError: (message: string) => void;
};

async function fetchGoogleConfirmNonce(): Promise<string> {
  return (await fetchFirstPasswordNonce()).nonce;
}

export function ConfirmItsYou({ provider, onProof, onError }: { provider: ConfirmProvider } & ConfirmEvents) {
  const google = provider === "GOOGLE" && googleClientId() !== null;
  const oidc = provider === "GOOGLE" ? null : (configuredOidcProviders().find((item) => item.id === provider) ?? null);

  return (
    <div className="grid gap-3 rounded-card bg-sunk px-4 py-4">
      <p className="font-ui text-ui font-normal text-ink-1">{confirmPrompt(provider)}</p>
      {google ? <GoogleConfirm onProof={onProof} onError={onError} /> : null}
      {oidc ? <ProviderConfirm provider={oidc} onError={onError} /> : null}
      {!google && !oidc ? <p className="font-ui text-label text-ink-2">{NO_PROVIDER_HERE}</p> : null}
    </div>
  );
}

function GoogleConfirm({ onProof, onError }: ConfirmEvents) {
  const { clientId, nonce, failed, renew } = useGoogleNonce(fetchGoogleConfirmNonce);
  const events = useRef({ onProof, onError });
  useEffect(() => {
    events.current = { onProof, onError };
  });

  if (!clientId) return null;
  return (
    <>
      <GoogleSignInButton
        clientId={clientId}
        nonce={nonce}
        disabled={!nonce}
        onCredential={(credential) => events.current.onProof({ googleIdToken: credential })}
        onLoadError={() => events.current.onError(GOOGLE_UNREACHABLE)}
      />
      {failed ? (
        <Button variant="text" onClick={renew} className="justify-self-center">
          Retry Google sign-in
        </Button>
      ) : null}
    </>
  );
}

function ProviderConfirm({ provider, onError }: { provider: OidcProvider; onError: (message: string) => void }) {
  const [leaving, setLeaving] = useState(false);

  async function leaveForProvider() {
    setLeaving(true);
    try {
      const { nonce } = await fetchFirstPasswordNonce();
      window.location.assign(await beginSignIn(provider, window.location.origin, { rawNonce: nonce, purpose: "confirm" }));
    } catch (err) {
      setLeaving(false);
      onError(err instanceof ApiError ? err.message : callbackErrorMessage(provider.id, null));
    }
  }

  return (
    <ActionGroup fill>
      <Button variant="quiet" busy={leaving} busyLabel="Opening" onClick={() => void leaveForProvider()}>
        {`Continue with ${provider.label}`}
      </Button>
    </ActionGroup>
  );
}
