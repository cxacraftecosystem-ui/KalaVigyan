"use client";

import { PicturePreview } from "@/components/contributions/PicturePreview";
import { Field, TextArea, TextInput } from "@/components/FormControls";
import type { BatchWords } from "@/lib/imageBatch";
import type { ImageOrigin } from "@/lib/imageContributionContract";
import { replaced } from "@/lib/ownProposalsContract";

type Batch = {
  files: readonly File[];
  words: readonly BatchWords[];
  origin: ImageOrigin;
  generator: string;
  onChange: (words: BatchWords[]) => void;
};

export function BatchPictures({ files, words, origin, generator, onChange }: Batch) {
  const ai = origin === "AI_GENERATED";
  return (
    <ol className="grid gap-6" aria-label="The pictures you give" data-testid="batch-pictures">
      {files.map((file, index) => {
        const own = words[index];
        if (!own) return null;
        const set = (field: keyof BatchWords) => (value: string) => onChange(replaced([...words], index, { ...own, [field]: value }));
        return (
          <li key={`${file.name}-${index}`} className="grid gap-4 border-t border-rule pt-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <PicturePreview file={file} origin={origin} generator={generator} caption={own.caption} altText={own.altText} />
            <div className="grid content-start gap-4">
              <p className="kicker">Picture {index + 1} of {files.length}</p>
              <Field label="Caption">
                <TextInput value={own.caption} onChange={(event) => set("caption")(event.target.value)} maxLength={300} />
              </Field>
              <Field label="Description for readers who cannot see it">
                <TextArea value={own.altText} onChange={(event) => set("altText")(event.target.value)} maxLength={300} rows={2} />
              </Field>
              {ai ? (
                <Field label="Prompt">
                  <TextArea value={own.prompt} onChange={(event) => set("prompt")(event.target.value)} maxLength={4000} rows={3} />
                </Field>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
