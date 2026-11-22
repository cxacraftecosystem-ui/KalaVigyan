"use client";

import { useMemo, useState, type FormEvent } from "react";
import { Presentation } from "lucide-react";

import { FormAlert } from "@/components/auth/FormAlert";
import { Field, TextInput } from "@/components/FormControls";
import { useMoveFocus, type MoveFocus } from "@/components/hooks/useMoveFocus";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { MoveButtons } from "@/components/ui/MoveButtons";
import { Toggle } from "@/components/ui/Toggle";
import { apiErrorMessage } from "@/lib/api";
import type { ExplainerVersionDocument } from "@/lib/learningContract";
import { buildLesson } from "@/lib/lessonApi";
import { inListedOrder, moveItem, movedText } from "@/lib/listOrder";
import type { LessonPack } from "@/lib/lessonContract";
import { chosenInOrder, LESSON_SECTIONS_MAX, lessonRequest, lessonSections, type LessonSection } from "@/lib/lessonView";
import { cn } from "@/lib/utils";

const BUILD_FAILED = "Couldn't build the lesson. Try again.";

type SectionPlace = { index: number; count: number; focus: MoveFocus; onMove: (from: number, to: number) => void };

function SectionChoice({ section, on, onFlip, place }: { section: LessonSection; on: boolean; onFlip: () => void; place: SectionPlace }) {
  return (
    <div className="flex min-w-0 items-center gap-2" data-testid="lesson-section" data-chosen={on ? "true" : "false"} data-section-id={section.id}>
      <label
        className={cn(
          "flex min-h-12 min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-control border px-3 py-2 transition-colors duration-state",
          on ? "border-indigo bg-indigo-wash" : "border-rule-strong bg-raised hover:border-ink-1"
        )}
      >
        <input type="checkbox" className="h-4 w-4 shrink-0 accent-indigo" checked={on} onChange={onFlip} />
        <span className="min-w-0 flex-1 break-words font-ui text-ui text-ink-1">{section.title}</span>
      </label>
      <MoveButtons name={section.title} index={place.index} count={place.count} register={(direction, node) => place.focus.register(section.id, direction, node)} onMove={place.onMove} />
    </div>
  );
}

function useSectionOrder(sections: readonly LessonSection[]) {
  const [ids, setIds] = useState<string[]>(() => sections.map((section) => section.id));
  const [announcement, setAnnouncement] = useState("");
  const ordered = useMemo(() => inListedOrder(sections, ids), [sections, ids]);
  const focus = useMoveFocus(ids);
  function move(from: number, to: number) {
    if (to < 0 || to >= ordered.length) return;
    setIds(moveItem(ordered.map((section) => section.id), from, to));
    setAnnouncement(movedText(ordered[from].title, to, ordered.length));
    focus.followMove(ordered[from].id, from, to, ordered.length);
  }
  return { ordered, announcement, focus, move };
}

function useChosen(sections: readonly LessonSection[]) {
  const [chosen, setChosen] = useState<ReadonlySet<string>>(() => new Set(sections.slice(0, LESSON_SECTIONS_MAX).map((section) => section.id)));
  function flip(id: string) {
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else if (next.size < LESSON_SECTIONS_MAX) next.add(id);
      return next;
    });
  }
  return [chosen, flip] as const;
}

export function LessonBuilder({ document, onBuilt }: { document: ExplainerVersionDocument; onBuilt: (pack: LessonPack) => void }) {
  const sections = useMemo(() => lessonSections(document.explainer), [document]);
  const [title, setTitle] = useState("");
  const [chosen, flip] = useChosen(sections);
  const order = useSectionOrder(sections);
  const [quiz, setQuiz] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = { explainerId: document.mark.explainerId, version: document.mark.version };
  const request = lessonRequest(ref, title, chosenInOrder(order.ordered, chosen), quiz);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!request || busy) return;
    setBusy(true);
    setError(null);
    try {
      onBuilt(await buildLesson(request));
    } catch (cause) {
      setError(apiErrorMessage(cause, BUILD_FAILED));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid min-w-0 max-w-measure gap-6 border-t border-ink-1 pt-6" data-testid="lesson-builder">
      <Field label="Title">
        <TextInput value={title} maxLength={200} placeholder={document.explainer.question} onChange={(event) => setTitle(event.target.value)} />
      </Field>
      <fieldset className="grid min-w-0 gap-2">
        <legend className="field-label mb-2">Sections · {chosen.size} chosen</legend>
        {sections.length === 0 ? <p className="font-ui text-ui font-normal text-ink-2">A lesson takes the answer&apos;s finished sections. Let the answer finish, then open this page again.</p> : null}
        {order.ordered.map((section, index) => (
          <SectionChoice key={section.id} section={section} on={chosen.has(section.id)} onFlip={() => flip(section.id)} place={{ index, count: order.ordered.length, focus: order.focus, onMove: order.move }} />
        ))}
        <p aria-live="polite" className="sr-only">
          {order.announcement}
        </p>
      </fieldset>
      <Toggle label="Add a quiz" description="Questions from the chosen sections, with an answer key." checked={quiz} onChange={setQuiz} />
      {error ? <FormAlert>{error}</FormAlert> : null}
      <ActionGroup fill>
        <Button type="submit" variant="primary" disabled={!request} busy={busy} busyLabel="Building" data-testid="lesson-build">
          <Presentation aria-hidden />
          Build the lesson
        </Button>
      </ActionGroup>
    </form>
  );
}
