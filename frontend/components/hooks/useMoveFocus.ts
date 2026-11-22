"use client";

import { useEffect, useRef } from "react";

import { usableAfterMove, type MoveDirection } from "@/lib/listOrder";

export type MoveFocus = {
  register: (key: string, direction: MoveDirection, node: HTMLButtonElement | null) => void;
  followMove: (key: string, from: number, to: number, count: number) => void;
};

export function useMoveFocus(order: unknown): MoveFocus {
  const pending = useRef<string | null>(null);
  const buttons = useRef(new Map<string, HTMLButtonElement | null>());

  useEffect(() => {
    const target = pending.current;
    if (!target) return;
    pending.current = null;
    buttons.current.get(target)?.focus();
  }, [order]);

  return {
    register: (key, direction, node) => buttons.current.set(`${key}:${direction}`, node),
    followMove: (key, from, to, count) => {
      pending.current = `${key}:${usableAfterMove(from, to, count)}`;
    }
  };
}
