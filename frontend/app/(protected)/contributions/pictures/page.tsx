"use client";

import { useCallback, useEffect, useState } from "react";
import { ImagePlus } from "lucide-react";

import { MyPictures } from "@/components/contributions/MyPictures";
import { PictureForm } from "@/components/contributions/PictureForm";
import { PageHeader } from "@/components/PageHeader";
import { apiErrorMessage } from "@/lib/api";
import { fetchMyImages, sentNotice, withdrawImage, type ImageContribution } from "@/lib/imageContributionContract";

export default function GivePicturePage() {
  const [items, setItems] = useState<ImageContribution[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await fetchMyImages());
      setError(null);
    } catch (cause) {
      setError(apiErrorMessage(cause, "Couldn't load your pictures. Reload the page."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function withdraw(item: ImageContribution) {
    setBusy(true);
    try {
      await withdrawImage(item.id);
      setNotice("The picture is taken back.");
      await load();
    } catch (cause) {
      setError(apiErrorMessage(cause, "Couldn't take the picture back. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Give a picture"
        description="A photograph, a drawing or an AI-made illustration of a craft. AI-made pictures are always shown as illustrations."
        icon={<ImagePlus className="h-5 w-5" aria-hidden />}
      />
      <div className="grid gap-12">
        <PictureForm
          onSent={(sent) => {
            setNotice(sentNotice(sent));
            void load();
          }}
        />
        {notice ? <p role="status" className="text-ui font-ui text-ink-1">{notice}</p> : null}
        {error ? <p role="alert" className="text-ui font-ui text-error">{error}</p> : null}
        <section className="grid gap-4" aria-labelledby="my-pictures-h">
          <h2 id="my-pictures-h" className="text-h3 font-reading text-ink-1">Your pictures</h2>
          <MyPictures items={items} busy={busy} onWithdraw={(item) => void withdraw(item)} />
        </section>
      </div>
    </>
  );
}
