"use client";

import { useState } from "react";

import type { Contributions } from "@/components/contributions/useContributions";
import { apiErrorMessage } from "@/lib/api";
import { termsAccepted, withTerms, type OpenTask } from "@/lib/ownProposalsContract";
import {
  fetchTranslationView,
  filledPassages,
  PASSAGES_SHOWN,
  sendTranslation,
  taskPage,
  translationBundle,
  type BundleReply,
  type PassageView,
  type TranslationView
} from "@/lib/translationContract";

const READ_FAILED = "Couldn't read the page's passages. Pick the task again.";
const SEND_FAILED = "Couldn't send the translation. Nothing was stored; try again.";
const NOTHING_WRITTEN = "Translate at least one passage first.";

export type TranslationWork = {
  task: OpenTask | null;
  view: TranslationView | null;
  passages: PassageView[];
  drafts: Record<string, Record<number, string>>;
  ticked: boolean;
  busy: boolean;
  problems: string[];
  reply: BundleReply | null;
  sent: string[];
  startFrom: (task: OpenTask) => Promise<void>;
  write: (key: string, at: number, value: string) => void;
  setTicked: (ticked: boolean) => void;
  send: (preview: boolean) => Promise<void>;
};

async function openPassages(task: OpenTask): Promise<{ view: TranslationView; passages: PassageView[] }> {
  const page = taskPage(task.key);
  if (!page) throw new Error(READ_FAILED);
  const held = await fetchTranslationView(page.kind, page.slug, page.language, "HELD");
  const fresh = await fetchTranslationView(page.kind, page.slug, page.language, "TO_TRANSLATE");
  return { view: fresh, passages: [...held.passages, ...fresh.passages].slice(0, PASSAGES_SHOWN) };
}

export function useTranslationWork(contributions: Contributions): TranslationWork {
  const [task, setTask] = useState<OpenTask | null>(null);
  const [view, setView] = useState<TranslationView | null>(null);
  const [passages, setPassages] = useState<PassageView[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Record<number, string>>>({});
  const [ticked, setTicked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const [reply, setReply] = useState<BundleReply | null>(null);
  const [sent, setSent] = useState<string[]>([]);
  const terms = contributions.form?.terms ?? null;

  async function load(picked: OpenTask) {
    const opened = await openPassages(picked);
    setTask(picked);
    setView(opened.view);
    setPassages(opened.passages);
    setDrafts({});
  }

  async function startFrom(picked: OpenTask) {
    setBusy(true);
    setReply(null);
    setProblems([]);
    try {
      await load(picked);
    } catch (cause) {
      setProblems([apiErrorMessage(cause, READ_FAILED)]);
    } finally {
      setBusy(false);
    }
  }

  function write(key: string, at: number, value: string) {
    setDrafts((current) => ({ ...current, [key]: { ...current[key], [at]: value } }));
  }

  async function send(preview: boolean) {
    const filled = view ? filledPassages(passages, drafts) : [];
    const found = withTerms(filled.length ? [] : [NOTHING_WRITTEN], terms, ticked || preview);
    setProblems(found);
    if (found.length || !view || !terms) return;
    setBusy(true);
    setReply(null);
    try {
      if (!preview) contributions.setTerms(await termsAccepted(terms));
      const answer = await sendTranslation(translationBundle(view, filled, task?.key ?? null), preview);
      if (!preview && task) await load(task);
      setSent(filled.map((passage) => passage.key));
      setReply(answer);
    } catch (cause) {
      setProblems([apiErrorMessage(cause, SEND_FAILED)]);
    } finally {
      setBusy(false);
    }
  }

  return { task, view, passages, drafts, ticked, busy, problems, reply, sent, startFrom, write, setTicked, send };
}
