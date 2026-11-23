"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { AuthShell, OrDivider } from "@/components/auth/AuthShell";
import { OidcSignInButtons } from "@/components/auth/OidcSignInButtons";
import { AuthLinkLine, PasswordField } from "@/components/auth/PasswordField";
import { SignInRefusal } from "@/components/auth/SignInRefusal";
import { useGoogleNonce } from "@/components/auth/useGoogleNonce";
import { useOidcSignIn } from "@/components/auth/useOidcSignIn";
import { useAuth } from "@/components/AuthProvider";
import { FirstPasswordGate } from "@/components/FirstPasswordGate";
import { Field, TextInput } from "@/components/FormControls";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { TwoStepChallengeForm } from "@/components/TwoStepChallengeForm";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { ACCESS_STATUS_HEADER, accessRefusalKind, type AccessRefusalKind } from "@/lib/accessRoster";
import { rememberSignInReturn, signInReturnOnce } from "@/lib/sessionReturn";
import { SIGN_IN_HINT_HEADER, mustChangePassword, signInHintOf, type SignInHint } from "@/lib/signIn";
import { isTwoFactorChallenge, type TwoFactorChallenge } from "@/lib/twoFactor";
import type { User } from "@/lib/types";

type Failure = { message: string; refusal: AccessRefusalKind | null; hint: SignInHint };

function failureOf(err: unknown): Failure {
  const api = err instanceof ApiError ? err : null;
  return {
    refusal: accessRefusalKind(api?.status ?? 0, api ? api.headers?.get(ACCESS_STATUS_HEADER) : null),
    hint: signInHintOf(api ? api.headers?.get(SIGN_IN_HINT_HEADER) : null),
    message: api ? api.message : "Couldn't sign in. Check your connection and try again."
  };
}

function PasswordSignIn({ loading, disabled, onSubmit }: { loading: boolean; disabled: boolean; onSubmit: (email: string, password: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [shown, setShown] = useState(false);
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(email, password);
      }}
      className="grid gap-4"
    >
      <Field label="Email">
        <TextInput id="email" type="email" autoComplete="username" required placeholder="you@institution.ac.in" value={email} onChange={(event) => setEmail(event.target.value)} />
      </Field>
      <div className="grid gap-2">
        <PasswordField id="password" label="Password" autoComplete="current-password" revealed={shown} onReveal={() => setShown((value) => !value)} value={password} onChange={setPassword} minLength={8} placeholder="Your password" />
        <Link href="/forgot-password" className="kv-link justify-self-end font-ui text-ui">
          Forgot your password?
        </Link>
      </div>
      <ActionGroup fill className="mt-2">
        <Button type="submit" variant="primary" busy={loading} busyLabel="Signing in" disabled={disabled}>
          Sign in
        </Button>
      </ActionGroup>
    </form>
  );
}

function OtherWays({ google, oidc, busy, onGoogleCredential, onGoogleLoadError }: { google: ReturnType<typeof useGoogleNonce>; oidc: ReturnType<typeof useOidcSignIn>; busy: boolean; onGoogleCredential: (credential: string) => void; onGoogleLoadError: () => void }) {
  return (
    <>
      {google.clientId || oidc.providers.length > 0 ? <OrDivider /> : null}
      <div className="grid gap-2.5">
        {google.clientId ? (
          <>
            <GoogleSignInButton clientId={google.clientId} nonce={google.nonce} disabled={!google.nonce} onCredential={onGoogleCredential} onLoadError={onGoogleLoadError} />
            {google.failed ? (
              <button type="button" onClick={google.renew} className="kv-link justify-self-center font-ui text-label">
                Retry Google sign-in
              </button>
            ) : null}
          </>
        ) : null}
        <OidcSignInButtons providers={oidc.providers} disabled={busy} onStart={(provider) => void oidc.start(provider)} />
      </div>
    </>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const { login, loginWithGoogle, logout, markPasswordChanged, user } = useAuth();
  const { toast } = useToast();
  const google = useGoogleNonce();
  const [challenge, setChallenge] = useState<string | null>(null);
  const [doorPassword, setDoorPassword] = useState("");
  const [failure, setFailure] = useState<Failure | null>(null);
  const [loading, setLoading] = useState(false);
  const signingIn = useRef(false);
  const [landing] = useState(() => signInReturnOnce());
  const passwordGate = mustChangePassword(user) ? user : null;

  useEffect(() => {
    rememberSignInReturn(window.location.search);
  }, []);

  useEffect(() => {
    if (user && !signingIn.current && !passwordGate && !challenge) router.replace(landing());
  }, [challenge, landing, passwordGate, router, user]);

  const describeFailure = useCallback((err: unknown) => setFailure(failureOf(err)), []);

  const proceed = useCallback(
    (outcome: User | TwoFactorChallenge) => {
      if (isTwoFactorChallenge(outcome)) {
        setChallenge(outcome.challenge_token);
        return;
      }
      if (mustChangePassword(outcome)) return;
      router.replace(landing());
    },
    [landing, router]
  );

  const oidc = useOidcSignIn({
    onStart: () => {
      setDoorPassword("");
      setFailure(null);
      signingIn.current = true;
    },
    onSignedIn: proceed,
    onFailure: describeFailure,
    onMessage: (message) => setFailure({ message, refusal: null, hint: null }),
    onSettled: () => {
      signingIn.current = false;
    }
  });

  const onGoogleCredential = useCallback(
    async (credential: string) => {
      setDoorPassword("");
      setFailure(null);
      signingIn.current = true;
      try {
        proceed(await loginWithGoogle(credential, google.nonce));
      } catch (err) {
        describeFailure(err);
      } finally {
        signingIn.current = false;
        google.renew();
      }
    },
    [describeFailure, google, loginWithGoogle, proceed]
  );

  async function submit(email: string, password: string) {
    setLoading(true);
    setFailure(null);
    signingIn.current = true;
    setDoorPassword(password);
    try {
      proceed(await login(email, password));
    } catch (err) {
      setDoorPassword("");
      describeFailure(err);
    } finally {
      signingIn.current = false;
      setLoading(false);
    }
  }

  const subtitle = passwordGate || challenge ? "One more step" : "Sign in to your account";

  return (
    <AuthShell title="Welcome back" subtitle={subtitle}>
      {passwordGate ? (
        <FirstPasswordGate
          currentPassword={doorPassword}
          onDone={() => {
            setDoorPassword("");
            markPasswordChanged();
            router.replace(landing());
          }}
          onSignOut={() => {
            setDoorPassword("");
            logout().catch(() => undefined);
          }}
        />
      ) : challenge ? (
        <TwoStepChallengeForm
          challengeToken={challenge}
          onSignedIn={(account) => {
            setChallenge(null);
            if (!mustChangePassword(account)) router.replace(landing());
          }}
          onCancel={() => {
            setChallenge(null);
            setDoorPassword("");
          }}
        />
      ) : (
        <>
          {failure ? <SignInRefusal kind={failure.refusal} hint={failure.hint} message={failure.message} /> : null}
          <PasswordSignIn loading={loading} disabled={oidc.busy} onSubmit={(email, password) => void submit(email, password)} />
          <OtherWays
            google={google}
            oidc={oidc}
            busy={loading || oidc.busy}
            onGoogleCredential={(credential) => void onGoogleCredential(credential)}
            onGoogleLoadError={() => toast({ title: "Couldn't load Google sign-in", description: "Check your connection and reload.", tone: "error", duration: 0 })}
          />
          <AuthLinkLine>
            New here?{" "}
            <Link href="/signup" className="kv-link">
              Request access
            </Link>
          </AuthLinkLine>
        </>
      )}
    </AuthShell>
  );
}
