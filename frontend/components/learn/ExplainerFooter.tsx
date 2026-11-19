"use client";

import { useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowRight, GitCompareArrows } from "lucide-react";

import { QuizView } from "@/components/answer/learning/QuizView";
import { useRemote } from "@/components/hooks/useRemote";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Accordion } from "@/components/ui/Accordion";
import { Button, buttonLook } from "@/components/ui/button";
import { askable, QUESTION_MAX } from "@/lib/askRequest";
import { compareSuggestions } from "@/lib/comparePage";
import type { Understood } from "@/lib/explainerContract";
import type { ExplainerState } from "@/lib/explainerState";
import { countNoun } from "@/lib/format";
import { fetchExplainerQuiz } from "@/lib/learningApi";

export function FollowUpBox({ onAsk }: { onAsk: (question: string) => void }) {
  const [question, setQuestion] = useState("");
  const ready = askable(question);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    onAsk(question.trim());
    setQuestion("");
  }
  return (
    <form onSubmit={submit} className="grid min-w-0 gap-3 border-t border-ink-1 pt-5" data-testid="follow-up">
      <label htmlFor="follow-up-question" className="font-reading text-h3 text-ink-1">
        Ask a follow-up
      </label>
      <textarea
        id="follow-up-question"
        rows={2}
        maxLength={QUESTION_MAX}
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        placeholder="What else would you like to know?"
        className="kv-input min-h-20 resize-y"
      />
      <ActionGroup fill>
        <Button type="submit" variant="quiet" disabled={!ready}>
          Add to this explainer
          <ArrowRight className="rtl:-scale-x-100" aria-hidden />
        </Button>
      </ActionGroup>
    </form>
  );
}

export function CompareLinks({ understood }: { understood: Understood }) {
  const links = compareSuggestions(understood.crafts, understood.candidates);
  if (links.length === 0) return null;
  return (
    <nav aria-label="Compare" className="flex min-w-0 flex-wrap gap-2" data-testid="compare-links">
      {links.map((link) => (
        <Link key={link.href} href={link.href} {...buttonLook({ variant: "quiet", size: "sm", className: "max-w-full" })}>
          <GitCompareArrows aria-hidden />
          <span className="min-w-0 truncate">{link.label}</span>
        </Link>
      ))}
    </nav>
  );
}

export function SelfCheck({ answerId, reduce }: { answerId: string; reduce: boolean }) {
  const load = useMemo(() => () => fetchExplainerQuiz(answerId), [answerId]);
  const quiz = useRemote(load);
  if (!quiz.data) return null;
  return (
    <div data-testid="self-check">
      <Accordion title="Check yourself" subtitle={countNoun(quiz.data.quiz.questions.length, "question")}>
        <QuizView block={quiz.data.quiz} reduce={reduce} />
      </Accordion>
    </div>
  );
}

export function ExplainerNext({ state, canFollow, onFollowUp, reduce }: { state: ExplainerState; canFollow: boolean; onFollowUp: (question: string) => void; reduce: boolean }) {
  return (
    <div className="grid min-w-0 gap-6" data-testid="explainer-next">
      {state.understood ? <CompareLinks understood={state.understood} /> : null}
      {state.phase === "done" && state.answerId ? <SelfCheck answerId={state.answerId} reduce={reduce} /> : null}
      {canFollow ? <FollowUpBox onAsk={onFollowUp} /> : null}
    </div>
  );
}
