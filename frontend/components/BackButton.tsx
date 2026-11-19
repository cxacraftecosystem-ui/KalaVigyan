"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

import { IconButton } from "@/components/ui/IconButton";
import { useLeaveInterceptor } from "@/components/UnsavedChangesGuard";

export function BackButton({ href }: { href?: string }) {
  const router = useRouter();
  const interceptLeave = useLeaveInterceptor();
  return (
    <IconButton
      label="Go back"
      edge
      icon={<ArrowLeft className="h-5 w-5 rtl:-scale-x-100" />}
      onClick={() => {
        const go = href ? () => router.push(href) : () => router.back();
        if (interceptLeave(go)) return;
        go();
      }}
    />
  );
}
