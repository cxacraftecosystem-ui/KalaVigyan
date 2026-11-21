import { TextLink } from "@/components/ui/TextLink";
import { documentLanguagePath, readLanguages, TEXT_SCRIPTS, type PageKind, type PageLanguage } from "@/lib/documentLanguages";
import { ENGLISH, type DocumentTranslation } from "@/lib/monographDocument";

import "./documentLanguage.css";

export type DocumentLanguagesProps = {
  kind: PageKind;
  slug: string;
  current: string;
  languages: readonly PageLanguage[];
  translation?: DocumentTranslation;
};

const ENGLISH_NAME = "English";

function LanguageName({ language }: { language: PageLanguage }) {
  return (
    <>
      <span lang={language.code} dir={language.direction} data-script={TEXT_SCRIPTS[language.code]} className="ui">
        {language.autonym}
      </span>
      <span className="text-ink-3"> {language.label}</span>
    </>
  );
}

function Choice({ kind, slug, current, language }: { kind: PageKind; slug: string; current: string; language: PageLanguage | null }) {
  const code = language?.code ?? ENGLISH;
  const name = language ? <LanguageName language={language} /> : ENGLISH_NAME;
  if (code === current) {
    return (
      <span aria-current="page" className="font-medium text-ink-1">
        {name}
      </span>
    );
  }
  return <TextLink href={documentLanguagePath(kind, slug, code)}>{name}</TextLink>;
}

function translationNote(language: PageLanguage, translation: DocumentTranslation): string {
  return `${translation.translated} of ${translation.passages} passages read in ${language.label}, each translated from its English sentence with its citations; the others read in English and say so.`;
}

export function DocumentLanguages({ kind, slug, current, languages, translation }: DocumentLanguagesProps) {
  const read = readLanguages(languages);
  if (!read.length) return null;
  const shown = read.find((language) => language.code === current) ?? null;
  return (
    <nav aria-label="Languages of this page" className="mx-auto w-full max-w-content px-4 pt-3 sm:px-6 md:px-10 rail:px-12 xl:px-16">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 font-ui text-label text-ink-2">
        <span className="text-ink-3" aria-hidden="true">
          Read this page in
        </span>
        <ul className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <li>
            <Choice kind={kind} slug={slug} current={current} language={null} />
          </li>
          {read.map((language) => (
            <li key={language.code}>
              <Choice kind={kind} slug={slug} current={current} language={language} />
            </li>
          ))}
        </ul>
      </div>
      {shown && translation ? <p className="mt-1 max-w-measure font-ui text-label text-ink-3">{translationNote(shown, translation)}</p> : null}
    </nav>
  );
}
