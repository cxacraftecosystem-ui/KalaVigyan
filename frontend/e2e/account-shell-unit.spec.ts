import { expect, test } from "@playwright/test";
import { createElement, isValidElement, type ReactElement, type ReactNode } from "react";

import { appFrame } from "@/components/AppShell";
import { readingFrame } from "@/components/shell/ReadingShell";
import { accountStepFor } from "@/lib/accountGate";
import type { User } from "@/lib/types";

const READER: User = { id: "u1", email: "ananya@iitkgp.ac.in", name: "Ananya", role: "RESEARCHER" };
const PAGE = createElement("article", { id: "the-page" });

function typesAbove(tree: ReactNode, page: ReactElement): unknown[] | null {
  const path: unknown[] = [];
  let node: ReactNode = tree;
  while (isValidElement(node) && node !== page) {
    path.push(node.type);
    node = (node.props as { children?: ReactNode }).children;
  }
  return node === page ? path : null;
}

test("a reading page keeps the same frame above it before and after the account is known, so it is not drawn twice", () => {
  const opening = typesAbove(readingFrame({ user: null, loading: true, onRetry: null }, PAGE), PAGE);
  const signedOut = typesAbove(readingFrame({ user: null, loading: false, onRetry: null }, PAGE), PAGE);
  const signedIn = typesAbove(readingFrame({ user: READER, loading: false, onRetry: null }, PAGE), PAGE);
  expect(opening).toHaveLength(2);
  expect(signedOut).toEqual(opening);
  expect(signedIn).toEqual(opening);
});

test("the ask page drawn before the account is known keeps its frame once the account arrives, and other pages wait", () => {
  const opening = typesAbove(appFrame({ user: null, loading: true, firstPaint: true, onRetry: null }, PAGE), PAGE);
  const known = typesAbove(appFrame({ user: READER, loading: false, firstPaint: true, onRetry: null }, PAGE), PAGE);
  expect(opening).toHaveLength(3);
  expect(known).toEqual(opening);
  expect(typesAbove(appFrame({ user: null, loading: true, firstPaint: false, onRetry: null }, PAGE), PAGE)).toBeNull();
  expect(typesAbove(appFrame({ user: READER, loading: false, firstPaint: false, onRetry: null }, PAGE), PAGE)).toEqual(opening);
});

test("the account gate asks nothing of a reader not yet known, and each of its steps in order of a signed-in account", () => {
  expect(accountStepFor(null)).toBeNull();
  expect(accountStepFor(READER)).toBeNull();
  expect(accountStepFor({ ...READER, mustChangePassword: true, twoFactorRequired: true })).toBe("first-password");
  expect(accountStepFor({ ...READER, role: "PROFESSOR", twoFactorRequired: true, twoFactorEnabled: false, profileRequired: true })).toBe("two-step");
  expect(accountStepFor({ ...READER, role: "PROFESSOR", twoFactorRequired: true, twoFactorEnabled: true, profileRequired: true })).toBe("first-entry");
  expect(accountStepFor({ ...READER, role: "STUDENT", guardianConsentRequired: true })).toBe("guardian");
});
