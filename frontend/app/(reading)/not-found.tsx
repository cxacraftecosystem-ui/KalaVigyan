"use client";

import { useLayoutEffect } from "react";

import { ErrorState } from "@/components/DeadEnd";
import { markNotFoundPage } from "@/lib/session";

export default function ReadingNotFound() {
  useLayoutEffect(() => {
    markNotFoundPage();
  }, []);
  return <ErrorState kind="not-found" />;
}
