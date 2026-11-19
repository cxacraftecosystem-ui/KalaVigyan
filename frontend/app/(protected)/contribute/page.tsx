"use client";

import { useCallback, useEffect, useState } from "react";

import { ConversationRun } from "@/components/artisan/ConversationRun";
import { ConversationSetup } from "@/components/artisan/ConversationSetup";
import { MyContributions } from "@/components/artisan/MyContributions";
import { FormAlert } from "@/components/auth/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { fetchAskConfig } from "@/lib/askConfig";
import { availabilityShape, type ConversationAvailability, type RelayConversationStarted } from "@/lib/conversationContract";
import { fetchProfile } from "@/lib/profileContract";
import { parseShape } from "@/lib/shape";
import { fetchContributions, type ContributionList } from "@/lib/testimonyContract";

const CONTRIBUTE_LINE = "Talk about your craft in the language you speak. A reviewer reads every line before it is shown, and you can take any line back.";

export default function ContributePage() {
  const [offered, setOffered] = useState<ConversationAvailability | null>(null);
  const [spoken, setSpoken] = useState<string | null>(null);
  const [listed, setListed] = useState<ContributionList | null>(null);
  const [started, setStarted] = useState<RelayConversationStarted | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    fetchAskConfig()
      .then((raw) => setOffered(parseShape(availabilityShape, (raw as { conversation?: unknown }).conversation)))
      .catch(() => setOffered(null));
    fetchProfile()
      .then((view) => setSpoken(view.artisan?.spokenLanguage ?? null))
      .catch(() => setSpoken(null));
    fetchContributions()
      .then(setListed)
      .catch(() => setFailed(true));
  }, []);

  useEffect(load, [load]);

  return (
    <>
      <PageHeader title="Your craft in your words" description={CONTRIBUTE_LINE} back={false} />
      <div className="grid gap-10">
        {offered && offered.configured && offered.transport === "RELAY" ? (
          <section aria-label="Record" className="grid max-w-measure gap-4 border-t border-ink-1 pt-5" data-testid="talk">
            {started ? (
              <ConversationRun started={started} onEnded={() => { setStarted(null); load(); }} />
            ) : (
              <ConversationSetup offered={offered} spoken={spoken} onAgreed={load} onStarted={setStarted} />
            )}
          </section>
        ) : null}
        {failed ? <FormAlert>Couldn&apos;t load what you shared. Reload the page.</FormAlert> : null}
        {listed ? <MyContributions listed={listed} onChanged={load} /> : null}
      </div>
    </>
  );
}
