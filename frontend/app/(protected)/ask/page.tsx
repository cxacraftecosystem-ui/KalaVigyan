"use client";

import { Suspense } from "react";
import { CircleAlert } from "lucide-react";

import { ExplainerView } from "@/components/answer/ExplainerView";
import { NotEnoughEvidence } from "@/components/answer/NotEnoughEvidence";
import { AnswerTools } from "@/components/ask/AnswerTools";
import { AskBox } from "@/components/ask/AskBox";
import { AskOptions } from "@/components/ask/AskOptions";
import { useAskScreen } from "@/components/ask/useAskScreen";
import { useExplainerLearning } from "@/components/ask/useExplainerLearning";
import { useAppReducedMotion } from "@/components/guide/useAppReducedMotion";
import { failureMessage } from "@/components/hooks/useRemote";
import { ExplainerNext } from "@/components/learn/ExplainerFooter";
import { VersionPicker } from "@/components/learn/ExplainerTools";
import { LoadingPanel, RetryPanel } from "@/components/RemotePanels";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";

const STARTERS = ["Why does alum fix madder dye on cotton?", "What happens to clay when terracotta is fired?", "How does indigo turn blue on the cloth?"];

export default function AskPage() {
  return (
    <Suspense fallback={null}>
      <AskScreen />
    </Suspense>
  );
}

function Starters({ onAsk }: { onAsk: (question: string) => void }) {
  return (
    <div className="grid gap-2">
      <p className="kicker">Try</p>
      <ActionGroup align="start">
        {STARTERS.map((starter) => (
          <button key={starter} type="button" className="kv-chip" onClick={() => onAsk(starter)}>
            {starter}
          </button>
        ))}
      </ActionGroup>
    </div>
  );
}

function AnswerFailed({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="mx-auto flex w-full max-w-measure flex-wrap items-center justify-between gap-3 rounded-control bg-error-wash px-4 py-3 font-ui text-ui text-ink-1">
      <span className="flex items-start gap-2">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-error" aria-hidden />
        {message}
      </span>
      <ActionGroup inline align="end">
        <Button variant="quiet" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </ActionGroup>
    </div>
  );
}

function AskScreen() {
  const reduce = useAppReducedMotion();
  const { state, round, config, question, setQuestion, language, dictation, busy, canAsk, options, understood, shownDepth, run, follow, load, stop, clear } = useAskScreen();
  const learning = useExplainerLearning({ state, load, follow, setQuestion });
  const started = state.phase !== "idle";
  const idle = !started && !learning.opening;
  const onFollowUp = (next: string) => {
    if (learning.canFollow) return learning.askFollowUp(next);
    clear();
    run(next, { languageChoice: state.language });
  };
  const research = () => run(state.question, { languageChoice: state.language, fresh: true });

  return (
    <div className="grid w-full min-w-0 gap-8">
      <div className="mx-auto grid w-full max-w-measure gap-5">
        {idle ? (
          <header className="pt-4 md:pt-12">
            <h1 className="font-headline text-h1 text-ink-1">What would you like to understand?</h1>
          </header>
        ) : null}
        {learning.opening && !started ? <h1 className="sr-only">Answer</h1> : null}
        <AskBox value={question} onChange={setQuestion} onSubmit={() => run(question)} onStop={stop} busy={busy} canAsk={canAsk} dictation={dictation} language={language} options={<AskOptions {...options} />} />
        {idle ? <Starters onAsk={(starter) => run(starter)} /> : null}
        {learning.failure ? <RetryPanel message={failureMessage({ cause: learning.failure }, "Couldn't open that explainer.")} onRetry={learning.retry} /> : null}
        {learning.opening && !learning.failure ? <LoadingPanel /> : null}
      </div>

      {state.phase === "failed" ? <AnswerFailed message={state.error ?? "Couldn't answer that."} onRetry={() => run(question)} /> : null}

      {started ? (
        <ExplainerView
          key={round}
          state={state}
          streaming={busy}
          languages={config.languages}
          depthLabel={shownDepth}
          change={understood}
          listenLanguages={config.listenLanguages}
          filmScore={config.filmScore}
          onFollowUp={onFollowUp}
          onFreshResearch={research}
          tools={learning.ref ? <AnswerTools explainer={learning.ref} /> : null}
          versions={learning.ref ? <VersionPicker choice={{ versions: learning.versions, viewing: state.mark, onPick: learning.pickVersion }} sections={state.sections} /> : null}
          footer={learning.ref ? <ExplainerNext state={state} canFollow={learning.canFollow} onFollowUp={learning.askFollowUp} reduce={reduce} /> : null}
        />
      ) : null}

      {state.phase === "empty" ? <NotEnoughEvidence onResearch={research} /> : null}
    </div>
  );
}
