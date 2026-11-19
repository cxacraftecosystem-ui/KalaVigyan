"use client";

import { useCallback, useEffect, useState, type RefObject } from "react";
import { useInView } from "framer-motion";

import { ApiError } from "@/lib/api";
import { fetchConformer } from "@/lib/conformer";
import { loadMoleculeViewer, webglAvailable, type MoleculeScene } from "@/lib/moleculeViewer";
import { isGone } from "@/lib/placeView";
import { ShapeError } from "@/lib/shape";

export type MoleculeStatus = "waiting" | "loading" | "ready" | "hidden" | "failed";
export type Molecule = { status: MoleculeStatus; scene: MoleculeScene | null; retry: () => void };

const NEAR_VIEW = { once: true, margin: "200px 0px" } as const;

type Shown = Omit<Molecule, "retry">;

export function moleculeFailure(cause: unknown): "hidden" | "failed" {
  return isGone({ cause }) || cause instanceof ShapeError ? "hidden" : "failed";
}

export function useMolecule(frameRef: RefObject<HTMLDivElement | null>, pubchemCid: number): Molecule {
  const inView = useInView(frameRef, NEAR_VIEW);
  const [round, setRound] = useState(0);
  const [shown, setShown] = useState<Shown>({ status: "waiting", scene: null });

  useEffect(() => {
    const element = frameRef.current;
    if (!inView || !element) return;
    if (!webglAvailable()) {
      setShown({ status: "hidden", scene: null });
      return;
    }
    let cancelled = false;
    let scene: MoleculeScene | null = null;
    setShown({ status: "loading", scene: null });
    Promise.all([fetchConformer(pubchemCid), loadMoleculeViewer()])
      .then(([sdf, viewer]) => {
        if (cancelled) return;
        scene = viewer.show(element, sdf);
        setShown({ status: scene ? "ready" : "hidden", scene });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        if (!(cause instanceof ApiError)) console.error(cause);
        setShown({ status: moleculeFailure(cause), scene: null });
      });
    return () => {
      cancelled = true;
      scene?.dispose();
    };
  }, [inView, pubchemCid, round, frameRef]);

  const retry = useCallback(() => setRound((value) => value + 1), []);
  return { ...shown, retry };
}
