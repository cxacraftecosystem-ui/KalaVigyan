"use client";

import { useState } from "react";

import { BatchPictures } from "@/components/contributions/BatchPictures";
import { PictureFactsPicker } from "@/components/contributions/PictureFactsPicker";
import { PicturePreview } from "@/components/contributions/PicturePreview";
import { Field, TextArea, TextInput } from "@/components/FormControls";
import { CraftPicker, type PickedCraft } from "@/components/onboarding/CraftPicker";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { apiErrorMessage } from "@/lib/api";
import { BATCH_PICTURES_MAX, batchProblems, emptyWords, sendBatch, type BatchWords } from "@/lib/imageBatch";
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
  type ImageDeclaration,
  type ImageOrigin
} from "@/lib/imageContributionContract";

const ORIGIN_OPTIONS = IMAGE_ORIGINS.map((value) => ({ value, label: ORIGIN_LABELS[value] }));
const SEVERAL_HINT = `${FORMATS_HINT} Choose up to ${BATCH_PICTURES_MAX} pictures of one craft to give them under one declaration.`;

type Shared = { craftSlug: string; origin: ImageOrigin; generator: string; claimIds: string[] };

export function PictureForm({ onSent }: { onSent: (sent: ImageContribution) => void }) {
  const [craft, setCraft] = useState<PickedCraft[]>([]);
  const [origin, setOrigin] = useState<ImageOrigin>("PHOTOGRAPH");
  const [generator, setGenerator] = useState("");
  const [facts, setFacts] = useState<string[]>([]);
  const [one, setOne] = useState<BatchWords>(emptyWords());
  const [files, setFiles] = useState<File[]>([]);
  const [words, setWords] = useState<BatchWords[]>([]);
  const [agreed, setAgreed] = useState(false);
  const { busy, problems, send } = useSending(onSent);
  const craftSlug = craft[0]?.slug ?? "";
  const ai = origin === "AI_GENERATED";
  const several = files.length > 1;
  const setOneField = (field: keyof BatchWords) => (value: string) => setOne({ ...one, [field]: value });

  function choose(chosen: File[]) {
    const kept = chosen.slice(0, BATCH_PICTURES_MAX);
    setFiles(kept);
    setWords(kept.map(() => emptyWords()));
  }

  async function submit() {
    const shared = { craftSlug, origin, generator, claimIds: facts };
    const done = await send(shared, several ? words : [one], files, agreed);
    if (!done) return;
    setCraft([]);
    setFacts([]);
    setOne(emptyWords());
    setGenerator("");
    choose([]);
    setAgreed(false);
  }

  return (
    <form className="grid gap-5" onSubmit={(event) => { event.preventDefault(); void submit(); }} data-testid="picture-form">
      <Field label="Craft">
        <CraftPicker picked={craft} onChange={(next) => { setCraft(next.slice(-1)); setFacts([]); }} />
      </Field>
      <SegmentedChoice label="What it is" value={origin} options={ORIGIN_OPTIONS} onChange={(next) => setOrigin(next as ImageOrigin)} disabled={busy} />
      {ai ? (
        <Field label="AI tool and model" hint="For example ChatGPT, gpt-image-1.">
          <TextInput value={generator} onChange={(event) => setGenerator(event.target.value)} maxLength={120} />
        </Field>
      ) : null}
      {craftSlug ? (
        <Field label={ai ? "The facts it shows" : "The facts it shows, if any"}>
          <PictureFactsPicker craftSlug={craftSlug} chosen={facts} onChange={setFacts} />
        </Field>
      ) : null}
      <Field label={several ? "Pictures" : "Picture"} hint={SEVERAL_HINT}>
        <input type="file" multiple accept={IMAGE_ACCEPT} className="text-ui font-ui text-ink-1" onChange={(event) => choose(Array.from(event.target.files ?? []))} />
      </Field>
      {several ? (
        <BatchPictures files={files} words={words} origin={origin} generator={generator} onChange={setWords} />
      ) : (
        <OneWords words={one} ai={ai} onChange={setOneField} preview={{ file: files[0] ?? null, origin, generator }} />
      )}
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
        <Button type="submit" busy={busy} busyLabel="Sending">{several ? `Give the ${files.length} pictures` : "Give the picture"}</Button>
      </ActionGroup>
    </form>
  );
}

type OneProps = {
  words: BatchWords;
  ai: boolean;
  onChange: (field: keyof BatchWords) => (value: string) => void;
  preview: { file: File | null; origin: ImageOrigin; generator: string };
};

function OneWords({ words, ai, onChange, preview }: OneProps) {
  return (
    <>
      {ai ? (
        <Field label="Prompt">
          <TextArea value={words.prompt} onChange={(event) => onChange("prompt")(event.target.value)} maxLength={4000} rows={3} />
        </Field>
      ) : null}
      <Field label="Caption">
        <TextInput value={words.caption} onChange={(event) => onChange("caption")(event.target.value)} maxLength={300} />
      </Field>
      <Field label="Description for readers who cannot see it">
        <TextArea value={words.altText} onChange={(event) => onChange("altText")(event.target.value)} maxLength={300} rows={2} />
      </Field>
      <PicturePreview {...preview} caption={words.caption} altText={words.altText} />
    </>
  );
}

function useSending(onSent: (sent: ImageContribution) => void) {
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  async function send(shared: Shared, words: BatchWords[], files: File[], agreed: boolean): Promise<boolean> {
    const found = [...sendProblems(shared, words, files), ...(agreed ? [] : ["Confirm the declaration."])];
    setProblems(found);
    if (found.length) return false;
    setBusy(true);
    try {
      const outcome = await sent(shared, words, files);
      outcome.sent.forEach(onSent);
      setProblems(outcome.problems);
      return !outcome.problems.length;
    } catch (cause) {
      setProblems([apiErrorMessage(cause, "Couldn't send the picture. Try again.")]);
      return false;
    } finally {
      setBusy(false);
    }
  }

  return { busy, problems, send };
}

function sendProblems(shared: Shared, words: BatchWords[], files: File[]): string[] {
  if (files.length > 1) return batchProblems({ ...shared, pictures: words }, files);
  const file = files[0];
  const filed = file ? fileProblem(file) : "Choose the picture.";
  return [...declarationProblems(oneDeclaration(shared, words[0])), ...(filed ? [filed] : [])];
}

async function sent(shared: Shared, words: BatchWords[], files: File[]): Promise<{ sent: ImageContribution[]; problems: string[] }> {
  const file = files[0];
  if (files.length > 1 || !file) return sendBatch({ ...shared, pictures: words }, files);
  const declared = await declareImage(oneDeclaration(shared, words[0]));
  return { sent: [await uploadImageFile(declared.id, file)], problems: [] };
}

function oneDeclaration(shared: Shared, words: BatchWords | undefined): ImageDeclaration {
  const own = words ?? emptyWords();
  return { ...shared, stageId: null, prompt: own.prompt, caption: own.caption, altText: own.altText };
}
