"use client";

import { Suspense, useCallback } from "react";
import { useParams } from "next/navigation";

import { useRemote, type RemoteFailure } from "@/components/hooks/useRemote";
import { PageHeader } from "@/components/PageHeader";
import { RemoteView } from "@/components/RemotePanels";
import { FieldTranscriptView } from "@/components/voices/FieldTranscriptView";
import { ApiError } from "@/lib/api";
import { fetchFieldTranscript } from "@/lib/fieldVoicesContract";
import { recordLoadFailure } from "@/lib/recordView";

const NOUN = "interview";

function transcriptFailure(failure: RemoteFailure): string {
  const cause = failure.cause;
  return cause instanceof ApiError ? recordLoadFailure(NOUN, cause.status, cause.message) : recordLoadFailure(NOUN, null);
}

export default function FieldInterviewPage() {
  return (
    <Suspense fallback={null}>
      <FieldInterviewScreen />
    </Suspense>
  );
}

function FieldInterviewScreen() {
  const { id } = useParams<{ id: string }>();
  const load = useCallback(() => fetchFieldTranscript(id), [id]);
  const remote = useRemote(id ? load : null);
  return (
    <div className="grid min-w-0 gap-4">
      <PageHeader title={remote.data?.title ?? "Field interview"} />
      <RemoteView remote={remote} failed={transcriptFailure}>
        {(transcript) => <FieldTranscriptView transcript={transcript} />}
      </RemoteView>
    </div>
  );
}
