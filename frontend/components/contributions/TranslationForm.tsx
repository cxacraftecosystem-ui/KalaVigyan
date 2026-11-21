"use client";

import { PassageEditor } from "@/components/contributions/PassageEditor";
import type { TranslationWork } from "@/components/contributions/useTranslationWork";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";

export function TranslationForm({ work }: { work: TranslationWork }) {
  const { view, passages } = work;
  if (!view) {
    return <p className="max-w-measure font-ui text-ui text-ink-2">Start from a page above: its passages to translate open here, each beside its English sentence.</p>;
  }
  const language = view.language;
  return (
    <section className="grid gap-4" aria-labelledby="translation-form-h">
      <div className="grid gap-1">
        <h2 id="translation-form-h" className="font-reading text-h3 text-ink-1">
          {view.title} in {language.label}
        </h2>
        <p className="font-ui text-label text-ink-3">
          {view.translated} of {view.passagesTotal} passages read in {language.label}; {view.waiting} wait for review and {view.toTranslate + view.held} are open.
        </p>
      </div>
      <ol className="grid gap-4">
        {passages.map((passage) => (
          <PassageEditor
            key={passage.key}
            passage={passage}
            language={language.code}
            label={language.label}
            given={work.drafts[passage.key] ?? {}}
            disabled={work.busy}
            onWrite={(at, value) => work.write(passage.key, at, value)}
          />
        ))}
      </ol>
      <ActionGroup>
        <Button type="button" variant="quiet" disabled={work.busy} onClick={() => void work.send(true)}>
          Preview the page
        </Button>
        <Button type="button" variant="primary" busy={work.busy} busyLabel="Sending" onClick={() => void work.send(false)}>
          Propose the translation
        </Button>
      </ActionGroup>
    </section>
  );
}
