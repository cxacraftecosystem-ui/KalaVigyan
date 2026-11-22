"use client";

import { ChevronDown, ChevronUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { MoveDirection } from "@/lib/listOrder";

export type MoveButtonsProps = {
  name: string;
  index: number;
  count: number;
  register: (direction: MoveDirection, node: HTMLButtonElement | null) => void;
  onMove: (from: number, to: number) => void;
};

function MoveButton({ direction, disabled, label, register, onMove }: { direction: MoveDirection; disabled: boolean; label: string; register: (node: HTMLButtonElement | null) => void; onMove: () => void }) {
  const Icon = direction === "up" ? ChevronUp : ChevronDown;
  return (
    <Button ref={register} variant="quiet" size="icon" disabled={disabled} aria-label={label} onClick={onMove} data-testid={`move-${direction}`}>
      <Icon className="size-4" aria-hidden />
    </Button>
  );
}

export function MoveButtons({ name, index, count, register, onMove }: MoveButtonsProps) {
  return (
    <>
      <MoveButton direction="up" disabled={index === 0} label={`Move ${name} up`} register={(node) => register("up", node)} onMove={() => onMove(index, index - 1)} />
      <MoveButton direction="down" disabled={index === count - 1} label={`Move ${name} down`} register={(node) => register("down", node)} onMove={() => onMove(index, index + 1)} />
    </>
  );
}
