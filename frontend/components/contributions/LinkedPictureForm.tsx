"use client";

import { useState } from "react";

import { Field, TextArea, TextInput } from "@/components/FormControls";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { ApiError, apiErrorMessage } from "@/lib/api";
import { PicturePreview } from "@/components/contributions/PicturePreview";
import { fileProblem, FORMATS_HINT, IMAGE_ACCEPT, IMAGE_DECLARATION, IMAGE_ORIGINS, ORIGIN_LABELS, type ImageContribution, type ImageOrigin } from "@/lib/imageContributionContract";
import { giveLinkedPicture, slotDeclarationProblems, type SlotDeclaration, type UploadLinkView } from "@/lib/uploadLinkContract";

const ORIGIN_OPTIONS = IMAGE_ORIGINS.map((value) => ({ value, label: ORIGIN_LABELS[value] }));
const EMPTY: SlotDeclaration = { origin: "PHOTOGRAPH", generator: "", prompt: "", caption: "", altText: "" };

type Sending = { token: string; view: UploadLinkView; onSent: (sent: ImageContribution) => void; onClosed: () => void };

export function LinkedPictureForm(props: Sending) {
  const [declaration, setDeclaration] = useState<SlotDeclaration>(EMPTY);
  const [file, setFile] = useState<File | null>(null);
  const [agreed, setAgreed] = useState(false);
  const { busy, problems, send } = useLinkedSend(props);

  return (
    <form className="grid gap-5" onSubmit={(event) => { event.preventDefault(); void send(declaration, file, agreed); }} data-testid="linked-picture-form">
      <DeclarationFields declaration={declaration} busy={busy} onChange={setDeclaration} />
      <Field label="Picture" hint={FORMATS_HINT}>
        <input type="file" accept={IMAGE_ACCEPT} className="text-ui font-ui text-ink-1" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      </Field>
      <PicturePreview file={file} origin={declaration.origin} generator={declaration.generator} caption={declaration.caption} altText={declaration.altText} />
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

function DeclarationFields({ declaration, busy, onChange }: { declaration: SlotDeclaration; busy: boolean; onChange: (next: SlotDeclaration) => void }) {
  const set = (field: keyof SlotDeclaration) => (value: string) => onChange({ ...declaration, [field]: value });
  return (
    <>
      <SegmentedChoice label="What it is" value={declaration.origin} options={ORIGIN_OPTIONS} onChange={(next) => set("origin")(next as ImageOrigin)} disabled={busy} />
      {declaration.origin === "AI_GENERATED" ? (
        <>
          <Field label="AI tool and model" hint="For example ChatGPT, gpt-image-1.">
            <TextInput value={declaration.generator} onChange={(event) => set("generator")(event.target.value)} maxLength={120} />
          </Field>
          <Field label="Prompt">
            <TextArea value={declaration.prompt} onChange={(event) => set("prompt")(event.target.value)} maxLength={4000} rows={3} />
          </Field>
        </>
      ) : null}
      <Field label="Caption">
        <TextInput value={declaration.caption} onChange={(event) => set("caption")(event.target.value)} maxLength={300} />
      </Field>
      <Field label="Description for readers who cannot see it">
        <TextArea value={declaration.altText} onChange={(event) => set("altText")(event.target.value)} maxLength={300} rows={2} />
      </Field>
    </>
  );
}

function useLinkedSend({ token, view, onSent, onClosed }: Sending) {
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  async function send(declaration: SlotDeclaration, file: File | null, agreed: boolean) {
    const filed = file ? fileProblem(file) : "Choose the picture.";
    const found = [...slotDeclarationProblems(view, declaration), ...(filed ? [filed] : []), ...(agreed ? [] : ["Confirm the declaration."])];
    setProblems(found);
    if (found.length || !file) return;
    setBusy(true);
    try {
      onSent(await giveLinkedPicture(token, declaration, file));
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 410) onClosed();
      else setProblems([apiErrorMessage(cause, "Couldn't send the picture. Try again.")]);
    } finally {
      setBusy(false);
    }
  }

  return { busy, problems, send };
}
