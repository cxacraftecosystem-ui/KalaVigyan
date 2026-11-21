"use client";

import { useCallback, useEffect, useState } from "react";

import { apiErrorMessage } from "@/lib/api";
import type { DocumentLanguageCode } from "@/lib/documentLanguages";
import { decideTranslation, fetchReaderLanguages, fetchReviewList, saveReaderLanguages, type ReviewList } from "@/lib/translationContract";

const READ_FAILED = "Couldn't read the translations waiting for review. Reload the page.";
const SAVE_FAILED = "Couldn't save the languages you read. Try again.";
const DECIDE_FAILED = "Couldn't record the decision. Reload the page and try again.";

export type TranslationReview = {
  reads: DocumentLanguageCode[];
  list: ReviewList | null;
  busy: boolean;
  error: string | null;
  toggle: (language: DocumentLanguageCode) => Promise<void>;
  decide: (id: string, approve: boolean, note: string | null) => Promise<void>;
};

export function useTranslationReview(): TranslationReview {
  const [reads, setReads] = useState<DocumentLanguageCode[]>([]);
  const [list, setList] = useState<ReviewList | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const [languages, waiting] = await Promise.all([fetchReaderLanguages(), fetchReviewList()]);
      setReads(languages);
      setList(waiting);
    } catch (cause) {
      setError(apiErrorMessage(cause, READ_FAILED));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function act(work: () => Promise<unknown>, failed: string) {
    setBusy(true);
    setError(null);
    try {
      await work();
      await reload();
    } catch (cause) {
      setError(apiErrorMessage(cause, failed));
    } finally {
      setBusy(false);
    }
  }

  const toggle = (language: DocumentLanguageCode) =>
    act(() => saveReaderLanguages(reads.includes(language) ? reads.filter((code) => code !== language) : [...reads, language]), SAVE_FAILED);
  const decide = (id: string, approve: boolean, note: string | null) => act(() => decideTranslation(id, approve, note), DECIDE_FAILED);

  return { reads, list, busy, error, toggle, decide };
}
