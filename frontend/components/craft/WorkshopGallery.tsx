"use client";

import { useId } from "react";

import { FieldListMore } from "@/components/craft/FieldListMore";
import { useFieldList } from "@/components/craft/useFieldList";
import { Plate } from "@/components/editorial/Plate";
import type { FieldVoicesList, PageFieldPhoto } from "@/lib/fieldVoicesContract";
import { FIRST_PHOTOS, GALLERY_HEADING, photoCaption, photoGroups, photosOf, rightsLine } from "@/lib/fieldVoicesView";

const PHOTOS_NOUN = "photographs";

function Credit({ photo }: { photo: PageFieldPhoto }) {
  return (
    <>
      {photo.credit}
      <span className="block">{rightsLine(photo)}</span>
    </>
  );
}

function FieldPhoto({ photo }: { photo: PageFieldPhoto }) {
  return (
    <li className="min-w-0" data-testid="field-photo">
      <Plate src={photo.imageUrl} alt={photo.alt} caption={photoCaption(photo)} credit={<Credit photo={photo} />} ratio={`${photo.width} / ${photo.height}`} />
    </li>
  );
}

export function WorkshopGallery({ first }: { first: FieldVoicesList }) {
  const list = useFieldList(first, photosOf, FIRST_PHOTOS);
  const headingId = useId();
  const listId = useId();
  if (list.total === 0) return null;
  return (
    <section aria-labelledby={headingId} className="grid min-w-0 gap-4 border-t border-ink-1 pt-4" data-testid="workshop-gallery">
      <h2 id={headingId} className="font-reading text-h3 text-ink-1">
        {GALLERY_HEADING}
      </h2>
      <div id={listId} className="grid min-w-0 gap-8">
        {photoGroups(list.shown).map((group) => (
          <section key={group.key} className="grid min-w-0 gap-3" data-testid="photo-group">
            <h3 className="font-ui text-h4 text-ink-1">{group.label}</h3>
            <ul className="grid min-w-0 items-start gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {group.photos.map((photo) => (
                <FieldPhoto key={photo.itemId} photo={photo} />
              ))}
            </ul>
          </section>
        ))}
      </div>
      <FieldListMore list={list} noun={PHOTOS_NOUN} controls={listId} />
    </section>
  );
}
