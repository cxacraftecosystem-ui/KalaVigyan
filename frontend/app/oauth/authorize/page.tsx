"use client";

import { useEffect, useState } from "react";

import { ConsentForm } from "@/components/oauth/ConsentForm";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { TextLink } from "@/components/ui/TextLink";
import { apiErrorMessage } from "@/lib/api";
import { authorizationQuery, consentBody, MISSING_REQUEST, navigableRedirect, needsTerms } from "@/lib/oauthConsent";
import {
  approveAuthorization,
  denyAuthorization,
  fetchAuthorizationReview,
  fetchTermsOfUse,
  type AuthorizationPrompt,
  type AuthorizationQuery,
  type McpScope,
  type TermsOfUse
} from "@/lib/oauthContract";

type View =
  | { state: "checking" }
  | { state: "stopped"; message: string }
  | { state: "returning" }
  | { state: "refused"; redirectTo: string }
  | { state: "asking"; query: AuthorizationQuery; prompt: AuthorizationPrompt };

const REFUSED = "KalaVigyan can't accept what the app asked for, so nothing was connected.";
const STOPPED = "Couldn't check this connection. Start it again from the app.";
const UNSAFE_RETURN = "The app's return address can't be opened from here.";
const CONNECT_FAILED = "Couldn't connect the app. Try again.";
const CANCEL_FAILED = "Couldn't tell the app you cancelled. Close this page and cancel in the app.";
const TERMS_FAILED = "Couldn't fetch the terms of use. Reload the page.";

function returnTo(url: string, show: (view: View) => void) {
  if (!navigableRedirect(url)) {
    show({ state: "stopped", message: UNSAFE_RETURN });
    return;
  }
  show({ state: "returning" });
  window.location.assign(url);
}

export default function AuthorizePage() {
  const [view, setView] = useState<View>({ state: "checking" });
  const [terms, setTerms] = useState<TermsOfUse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = authorizationQuery(window.location.search);
    if (!query) {
      setView({ state: "stopped", message: MISSING_REQUEST });
      return;
    }
    let cancelled = false;
    fetchAuthorizationReview(query)
      .then((review) => {
        if (cancelled) return;
        if (review.kind === "redirect") {
          setView({ state: "refused", redirectTo: review.redirectTo });
          return;
        }
        setView({ state: "asking", query, prompt: review });
        if (needsTerms(review)) fetchTermsOfUse().then(setTerms, () => setError(TERMS_FAILED));
      })
      .catch((cause) => {
        if (!cancelled) setView({ state: "stopped", message: apiErrorMessage(cause, STOPPED) });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function decide(send: () => Promise<{ redirectTo: string }>, failed: string) {
    setBusy(true);
    setError(null);
    try {
      returnTo((await send()).redirectTo, setView);
    } catch (cause) {
      setError(apiErrorMessage(cause, failed));
      setBusy(false);
    }
  }

  const asking = view.state === "asking" ? view : null;
  return (
    <>
      <PageHeader
        title={asking ? `Connect ${asking.prompt.clientName}` : "Connect an app"}
        description={
          asking
            ? `It will use KalaVigyan in your name, then return you to ${asking.prompt.redirectHost}. Connect only an app you added yourself.`
            : undefined
        }
        back={false}
      />
      {view.state === "checking" ? <Skeleton shape="lede" label="Checking the app" /> : null}
      {view.state === "returning" ? <p role="status" className="text-ui font-ui text-ink-2">Returning you to the app.</p> : null}
      {view.state === "stopped" ? <p role="alert" className="text-ui font-ui text-error">{view.message}</p> : null}
      {view.state === "refused" ? (
        <div className="grid justify-items-start gap-3">
          <p role="alert" className="text-ui font-ui text-error">{REFUSED}</p>
          <TextLink standalone onClick={() => returnTo(view.redirectTo, setView)}>
            Return to the app
          </TextLink>
        </div>
      ) : null}
      {asking ? (
        <ConsentForm
          prompt={asking.prompt}
          terms={terms}
          busy={busy}
          error={error}
          onApprove={(chosen: McpScope[]) =>
            void decide(() => approveAuthorization(consentBody(asking.query, asking.prompt, chosen)), CONNECT_FAILED)
          }
          onCancel={() => void decide(() => denyAuthorization(asking.query), CANCEL_FAILED)}
        />
      ) : null}
    </>
  );
}
