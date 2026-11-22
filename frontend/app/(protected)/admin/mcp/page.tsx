"use client";

import { Suspense } from "react";

import { McpActivityHeader, McpActivityScreen } from "./McpActivityScreen";

export default function McpActivityPage() {
  return (
    <Suspense fallback={<McpActivityHeader />}>
      <McpActivityScreen />
    </Suspense>
  );
}
