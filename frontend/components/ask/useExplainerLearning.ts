"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useRemote } from "@/components/hooks/useRemote";
import type { AskRequest } from "@/lib/answerStream";
import type { ExplainerRef, ExplainerState } from "@/lib/explainerState";
import { explainerRef, explainerStateOf, followUpRequest, knownVersions } from "@/lib/explainerVersions";
import { fetchExplainerDocument, fetchExplainerHistory } from "@/lib/learningApi";
import { EXPLAINER_PARAM, explainerHref, UPDATE_PARAM, updateFacets, VERSION_PARAM } from "@/lib/savedView";
import { positiveParam } from "@/lib/searchParams";

export type LearningStream = {
  state: ExplainerState;
  load: (state: ExplainerState) => void;
  follow: (request: AskRequest, ref: ExplainerRef) => Promise<void>;
  setQuestion: (question: string) => void;
};

const LATEST = "latest";
const BUSY_PHASES: ReadonlySet<ExplainerState["phase"]> = new Set(["idle", "asking", "streaming"]);

function shownKey(explainerId: string, version: number | null): string {
  return `${explainerId}:${version ?? LATEST}`;
}

function useStoredExplainer({ load, follow, setQuestion }: Omit<LearningStream, "state">) {
  const params = useSearchParams();
  const router = useRouter();
  const explainerId = params.get(EXPLAINER_PARAM);
  const version = positiveParam(params.get(VERSION_PARAM));
  const update = params.get(UPDATE_PARAM);
  const shown = useRef<string | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (!explainerId) {
      shown.current = null;
      return;
    }
    const key = shownKey(explainerId, version);
    if (shown.current === key) return;
    shown.current = key;
    setFailure(null);
    const facets = version === null ? updateFacets(update) : [];
    let cancelled = false;
    let settled = false;
    Promise.all([fetchExplainerDocument(explainerId, version), facets.length > 0 ? fetchExplainerHistory(explainerId) : Promise.resolve(null)])
      .then(([document, history]) => {
        settled = true;
        if (cancelled) return;
        load(explainerStateOf(document));
        setQuestion(history?.versions[0]?.question ?? document.explainer.question);
        if (!history || facets.length === 0) return;
        const ref = { explainerId, version: document.mark.version };
        router.replace(explainerHref(explainerId), { scroll: false });
        void follow(followUpRequest(ref, history.versions[0].question, facets), ref);
      })
      .catch((cause: unknown) => {
        settled = true;
        if (cancelled) return;
        shown.current = null;
        setFailure(cause);
      });
    return () => {
      cancelled = true;
      if (!settled && shown.current === key) shown.current = null;
    };
  }, [explainerId, version, update, round, load, follow, setQuestion, router]);

  const open = useCallback((id: string, next: number | null) => router.replace(explainerHref(id, next), { scroll: false }), [router]);
  const adopt = useCallback(
    (id: string) => {
      shown.current = shownKey(id, null);
      open(id, null);
    },
    [open]
  );
  const retry = useCallback(() => setRound((value) => value + 1), []);
  const reload = useCallback(() => {
    shown.current = null;
    setRound((value) => value + 1);
  }, []);
  return { failure, retry, reload, open, adopt, opening: explainerId !== null && failure === null };
}

function useHistory(explainerId: string | null) {
  const load = useMemo(() => (explainerId ? () => fetchExplainerHistory(explainerId) : null), [explainerId]);
  return useRemote(load).data;
}

function useRaceReload(state: ExplainerState, reload: () => void) {
  const waiting = state.reload && state.phase === "done";
  useEffect(() => {
    if (waiting) reload();
  }, [waiting, reload]);
}

export function useExplainerLearning(stream: LearningStream) {
  const { state, follow } = stream;
  const stored = useStoredExplainer(stream);
  useRaceReload(state, stored.reload);
  const ref = explainerRef(state);
  const history = useHistory(state.mark?.explainerId ?? null);
  const versions = knownVersions(history?.versions ?? [], state.mark);
  const latest = versions.at(-1)?.version ?? ref?.version ?? 0;
  const settled = !BUSY_PHASES.has(state.phase) && ref !== null;
  const canFollow = settled && ref.version >= latest;

  function askFollowUp(question: string) {
    if (!ref || !canFollow) return;
    stored.adopt(ref.explainerId);
    void follow(followUpRequest(ref, question), ref);
  }

  function pickVersion(next: number) {
    if (!ref) return;
    stored.open(ref.explainerId, next >= latest ? null : next);
  }

  return {
    ref: settled ? ref : null,
    versions,
    canFollow,
    askFollowUp,
    pickVersion,
    opening: stored.opening && state.phase === "idle",
    failure: stored.failure,
    retry: stored.retry
  };
}
