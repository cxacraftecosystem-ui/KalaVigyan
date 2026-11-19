"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

import { useModalFocus } from "@/components/hooks/useModalFocus";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { cn } from "@/lib/utils";

export type DialogTone = "neutral" | "danger" | "warning";

export type FieldDialogProps = {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  role?: "dialog" | "alertdialog";
  tone?: DialogTone;
  dismissible?: boolean;
  dismissOnBackdrop?: boolean;
  busy?: boolean;
  initialFocusRef?: RefObject<HTMLElement | null>;
  className?: string;
  surfaceClassName?: string;
  showClose?: boolean;
  zIndex?: number;
};

const DIALOG_LAYER = 90;

export function FieldDialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  role = "dialog",
  tone = "neutral",
  dismissible = true,
  dismissOnBackdrop,
  busy = false,
  initialFocusRef,
  className,
  surfaceClassName,
  showClose,
  zIndex = DIALOG_LAYER
}: FieldDialogProps) {
  const titleId = useId();
  const descriptionId = `${titleId}-desc`;
  const instanceId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const canDismiss = dismissible && !busy;
  const backdropCloses = dismissOnBackdrop ?? (role !== "alertdialog" && tone !== "danger");
  const callerSetsMaxWidth = /(?:^|\s)!?max-w-/.test(className ?? "");
  const onPanelKeyDown = useModalFocus({ id: instanceId, open, panelRef, onEscape: onClose, canEscape: canDismiss, initialFocusRef });

  if (!mounted || !open) return null;

  return createPortal(
    <div
      data-field-dialog-overlay=""
      className="kv-overlay"
      style={{ zIndex, paddingInlineEnd: "calc(1rem + var(--nav-scroll-gutter, 0px))" }}
      onMouseDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (canDismiss && backdropCloses) onClose();
      }}
    >
      <div
        ref={panelRef}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        data-field-dialog=""
        data-tone={tone}
        onKeyDown={onPanelKeyDown}
        className={cn("motion-enter relative outline-hidden", surfaceClassName ?? "kv-dialog", callerSetsMaxWidth || !surfaceClassName ? null : "max-w-md", className)}
      >
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="font-reading text-h3 text-ink-1">
              {title}
            </h2>
            {description ? (
              <div id={descriptionId} className="mt-2 font-ui text-ui-lg text-ink-2">
                {description}
              </div>
            ) : null}
            {children}
          </div>
          {(showClose ?? true) && dismissible ? (
            <button type="button" onClick={onClose} disabled={busy} aria-label="Close dialog" className="kv-close disabled:opacity-40">
              <X aria-hidden />
            </button>
          ) : null}
        </div>
        {footer ? (
          <ActionGroup align="end" className="mt-5">
            {footer}
          </ActionGroup>
        ) : null}
      </div>
    </div>,
    document.body
  );
}
