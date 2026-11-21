"use client";

import { Field, TextInput } from "@/components/FormControls";
import { TEXT_SCRIPTS, textDirection, type DocumentLanguageCode } from "@/lib/documentLanguages";
import type { PassageView } from "@/lib/translationContract";

export type PassageEditorProps = {
  passage: PassageView;
  language: DocumentLanguageCode;
  label: string;
  given: Record<number, string>;
  disabled: boolean;
  onWrite: (at: number, value: string) => void;
};

const HELD_NOTE = "The English changed after this passage was translated; the earlier translation reads:";

function textLabel(passage: PassageView, at: number): string {
  if (passage.cited.includes(at)) return `Text ${at + 1}, the sentence's last words, where its citation sits`;
  return `Text ${at + 1}`;
}

export function PassageEditor({ passage, language, label, given, disabled, onWrite }: PassageEditorProps) {
  return (
    <li className="grid gap-3 border-t border-rule pt-4" data-passage={passage.key}>
      <p lang="en" className="max-w-measure font-reading text-body-sm text-ink-1">
        {passage.english}
      </p>
      {passage.previous ? (
        <p className="max-w-measure font-ui text-label text-ink-3">
          {HELD_NOTE}{" "}
          <span lang={language} dir={textDirection(language)} data-script={TEXT_SCRIPTS[language]}>
            {passage.previous.join("")}
          </span>
        </p>
      ) : null}
      <div className="grid gap-3">
        {passage.texts.map((english, at) =>
          passage.fixed.includes(at) ? (
            <p key={at} className="font-ui text-label text-ink-2">
              Text {at + 1} stays as it stands: <i lang="en">{english}</i>
            </p>
          ) : (
            <Field key={at} label={`${textLabel(passage, at)} in ${label}`} hint={<span lang="en">{english}</span>}>
              <TextInput
                lang={language}
                dir={textDirection(language)}
                data-script={TEXT_SCRIPTS[language]}
                value={given[at] ?? ""}
                disabled={disabled}
                onChange={(event) => onWrite(at, event.target.value)}
              />
            </Field>
          )
        )}
      </div>
    </li>
  );
}
