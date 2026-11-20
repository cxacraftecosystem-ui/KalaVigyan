"use client";

import { useState } from "react";

import { PictureFactsPicker } from "@/components/contributions/PictureFactsPicker";
import { PicturePreview } from "@/components/contributions/PicturePreview";
import { Field, TextArea, TextInput } from "@/components/FormControls";
import { CraftPicker, type PickedCraft } from "@/components/onboarding/CraftPicker";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { apiErrorMessage } from "@/lib/api";
import {
  declarationProblems,
  declareImage,
  fileProblem,
  FORMATS_HINT,
  IMAGE_ACCEPT,
  IMAGE_DECLARATION,
  IMAGE_ORIGINS,
  ORIGIN_LABELS,
  uploadImageFile,
  type ImageContribution,
  type ImageOrigin
} from "@/lib/imageContributionContract";

const ORIGIN_OPTIONS = IMAGE_ORIGINS.map((value) => ({ value, label: ORIGIN_LABELS[value] }));

export function PictureForm({ onSent }: { onSent: (sent: ImageContribution) => void }) {
  const [craft, setCraft] = useState<PickedCraft[]>([]);
  const [origin, setOrigin] = useState<ImageOrigin>("PHOTOGRAPH");
  const [generator, setGenerator] = useState("");
  const [prompt, setPrompt] = useState("");
  const [facts, setFacts] = useState<string[]>([]);
  const [caption, setCaption] = useState("");
  const [altText, setAltText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const craftSlug = craft[0]?.slug ?? "";
  const ai = origin === "AI_GENERATED";

  async function send() {
    const declaration = { craftSlug, stageId: null, claimIds: facts, origin, generator, prompt, caption, altText };
    const found = [...declarationProblems(declaration), ...(file ? [fileProblem(file)].filter((p): p is string => Boolean(p)) : ["Choose the picture."]), ...(agreed ? [] : ["Confirm the declaration."])];
    setProblems(found);
    if (found.length || !file) return;
    setBusy(true);
    try {
      const declared = await declareImage(declaration);
      onSent(await uploadImageFile(declared.id, file));
      setCraft([]);
      setFacts([]);
      setCaption("");
      setAltText("");
      setGenerator("");
      setPrompt("");
      setFile(null);
      setAgreed(false);
    } catch (cause) {
      setProblems([apiErrorMessage(cause, "Couldn't send the picture. Try again.")]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="grid gap-5" onSubmit={(event) => { event.preventDefault(); void send(); }} data-testid="picture-form">
      <Field label="Craft">
        <CraftPicker picked={craft} onChange={(next) => { setCraft(next.slice(-1)); setFacts([]); }} />
      </Field>
      <SegmentedChoice label="What it is" value={origin} options={ORIGIN_OPTIONS} onChange={(next) => setOrigin(next as ImageOrigin)} disabled={busy} />
      {ai ? (
        <>
          <Field label="AI tool and model" hint="For example ChatGPT, gpt-image-1.">
            <TextInput value={generator} onChange={(event) => setGenerator(event.target.value)} maxLength={120} />
          </Field>
          <Field label="Prompt">
            <TextArea value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={4000} rows={3} />
          </Field>
        </>
      ) : null}
      {craftSlug ? (
        <Field label={ai ? "The facts it shows" : "The facts it shows, if any"}>
          <PictureFactsPicker craftSlug={craftSlug} chosen={facts} onChange={setFacts} />
        </Field>
      ) : null}
      <Field label="Caption">
        <TextInput value={caption} onChange={(event) => setCaption(event.target.value)} maxLength={300} />
      </Field>
      <Field label="Description for readers who cannot see it">
        <TextArea value={altText} onChange={(event) => setAltText(event.target.value)} maxLength={300} rows={2} />
      </Field>
      <Field label="Picture" hint={FORMATS_HINT}>
        <input type="file" accept={IMAGE_ACCEPT} className="text-ui font-ui text-ink-1" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      </Field>
      <PicturePreview file={file} origin={origin} generator={generator} caption={caption} altText={altText} />
      <label className="flex items-start gap-3 text-body-sm font-reading text-ink-2">
        <input type="checkbox" className="mt-1.5 h-4 w-4 shrink-0" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} />
        <span>{IMAGE_DECLARATION}</span>
      </label>
      {problems.length ? (
        <ul role="alert" className="grid gap-1 text-ui font-ui text-error">
          {problems.map((problem) => <li key={problem}>{problem}</li>)}
        </ul>
      ) : null}
      <ActionGroup align="start">
        <Button type="submit" busy={busy} busyLabel="Sending">Give the picture</Button>
      </ActionGroup>
    </form>
  );
}
