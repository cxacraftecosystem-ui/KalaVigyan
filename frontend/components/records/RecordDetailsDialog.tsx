"use client";

import type { ReactNode } from "react";

import { FieldDialog } from "@/components/dialogs/FieldDialog";
import { Button } from "@/components/ui/button";

export type RecordDetail = readonly [label: string, value: ReactNode | null];

export function RecordDetailsDialog({
  open,
  onClose,
  title,
  description,
  details,
  onUpdate,
  onDelete,
  children
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  details: RecordDetail[];
  onUpdate?: () => void;
  onDelete?: () => void;
  children?: ReactNode;
}) {
  return (
    <FieldDialog
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="quiet" onClick={onClose}>
            Close
          </Button>
          {onUpdate ? (
            <Button variant="primary" onClick={onUpdate}>
              Update
            </Button>
          ) : null}
          {onDelete ? (
            <Button variant="danger" data-danger onClick={onDelete}>
              Delete
            </Button>
          ) : null}
        </>
      }
    >
      <dl className="mt-5 grid border-t border-ink-1 font-ui text-ui font-normal">
        {details
          .filter(([, value]) => value !== null && value !== undefined && value !== "")
          .map(([label, value]) => (
            <div key={label} className="grid gap-0.5 border-b border-rule py-2.5 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
              <dt className="text-label text-ink-3">{label}</dt>
              <dd className="whitespace-pre-line break-words text-ink-1 tabular-nums lining-nums">{value}</dd>
            </div>
          ))}
      </dl>
      {children}
    </FieldDialog>
  );
}
