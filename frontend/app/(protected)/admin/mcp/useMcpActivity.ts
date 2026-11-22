"use client";

import { useEffect, useRef, useState } from "react";

import { fetchMcpActivity, type McpActivity, type McpScope } from "@/lib/mcpActivityContract";

const UNREAD = "The MCP activity could not be read. Try again.";

export type McpActivityState = { activity: McpActivity | null; error: string | null; retry: () => void };

export function useMcpActivity({ days, client, connection }: McpScope): McpActivityState {
  const [activity, setActivity] = useState<McpActivity | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [round, setRound] = useState(0);
  const generation = useRef(0);

  useEffect(() => {
    const mine = ++generation.current;
    fetchMcpActivity({ days, client, connection })
      .then((next) => {
        if (mine !== generation.current) return;
        setActivity(next);
        setError(null);
      })
      .catch((err) => {
        if (mine !== generation.current) return;
        setError(err instanceof Error ? err.message : UNREAD);
      });
  }, [days, client, connection, round]);

  return { activity, error, retry: () => setRound((value) => value + 1) };
}
