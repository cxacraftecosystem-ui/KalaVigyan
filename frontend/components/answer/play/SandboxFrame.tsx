"use client";

import { useLayoutEffect, useMemo, useRef, useState } from "react";

import { SANDBOX_ATTRIBUTE, type SimulationBlock } from "@/lib/explainerPlay";
import { FRAME_DEFAULT_HEIGHT, ownFrameHeight, sandboxDocument } from "@/lib/sandboxFrame";

export function SandboxFrame({ block }: { block: Pick<SimulationBlock, "title" | "html" | "values"> }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(FRAME_DEFAULT_HEIGHT);
  const srcDoc = useMemo(() => sandboxDocument(block.html, block.values), [block.html, block.values]);

  useLayoutEffect(() => {
    const listen = (event: MessageEvent) => {
      const next = ownFrameHeight(event, frame.current?.contentWindow);
      if (next !== null) setHeight(next);
    };
    window.addEventListener("message", listen);
    return () => window.removeEventListener("message", listen);
  }, []);

  return (
    <iframe
      ref={frame}
      sandbox={SANDBOX_ATTRIBUTE}
      srcDoc={srcDoc}
      title={block.title}
      className="block w-full min-w-0 max-w-full rounded-plate border border-rule bg-white"
      style={{ height }}
      data-testid="sandbox-frame"
    />
  );
}
