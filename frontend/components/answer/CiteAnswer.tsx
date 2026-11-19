"use client";

import { useMemo } from "react";

import { CiteThis } from "@/components/craft/CiteThis";
import { answerCitable, type CitedAnswer, type ReaderPlace } from "@/lib/answerCitation";
import { SHARED_ANSWER_PAGE } from "@/lib/shareContract";

function readerPlace(): ReaderPlace {
  const { origin, pathname } = window.location;
  return { origin, path: pathname.startsWith(SHARED_ANSWER_PAGE) ? pathname : null };
}

export function CiteAnswer({ id, answer }: { id: string; answer: CitedAnswer }) {
  const cite = useMemo(() => answerCitable(answer, readerPlace()), [answer]);
  return (
    <div id={id} className="mt-6" data-testid="cite-answer">
      <CiteThis cite={cite} />
    </div>
  );
}
