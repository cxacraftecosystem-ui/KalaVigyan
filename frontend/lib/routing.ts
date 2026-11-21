import { apiFetch } from "@/lib/api";

export type KeyState = "ABSENT" | "UNTESTED" | "PASSING" | "FAILING";

export type AiProviderId = "GEMINI" | "ANTHROPIC" | "OPENAI" | "DEEPSEEK" | "ELEVENLABS" | "VOYAGE";

export type RouteModel = {
  id: string;
  label: string;
  tasks: string[];
};

export type RouteProvider = {
  id: AiProviderId;
  name: string;
  keyName: string;
  keyState: KeyState;
  publicTextOnly: boolean;
  models: RouteModel[];
};

export type RouteRow = {
  provider: AiProviderId;
  model: string;
  enabled: boolean;
  keyState: KeyState;
  testedAt: string | null;
  testError: string | null;
};

export type TaskRoute = {
  task: string;
  label: string;
  publicText: boolean;
  routes: RouteRow[];
  effectiveChain: string[];
  normalisedNote: string | null;
};

export type RoutingState = {
  tasks: TaskRoute[];
  providers: RouteProvider[];
};

export function fetchRouting(): Promise<RoutingState> {
  return apiFetch<RoutingState>("/settings/ai-routing");
}

export function saveTaskRoute(task: string, routes: Pick<RouteRow, "provider" | "model" | "enabled">[]): Promise<TaskRoute> {
  return apiFetch<TaskRoute>(`/settings/ai-routing/${encodeURIComponent(task)}`, {
    method: "PUT",
    body: JSON.stringify({ routes })
  });
}

export function testTaskRoute(task: string, provider: AiProviderId, model: string): Promise<TaskRoute> {
  return apiFetch<TaskRoute>(`/settings/ai-routing/${encodeURIComponent(task)}/test`, {
    method: "POST",
    body: JSON.stringify({ provider, model })
  });
}

export function sameRoutes(a: readonly RouteRow[], b: readonly RouteRow[]): boolean {
  return (
    a.length === b.length &&
    a.every((row, index) => row.provider === b[index].provider && row.model === b[index].model && row.enabled === b[index].enabled)
  );
}

export function moveRoute<T>(list: readonly T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) return [...list];
  const next = [...list];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

export function routeKey(row: Pick<RouteRow, "provider" | "model">): string {
  return `${row.provider}:${row.model}`;
}

export function modelsForTask(providers: readonly RouteProvider[], task: TaskRoute): { provider: RouteProvider; model: RouteModel }[] {
  const out: { provider: RouteProvider; model: RouteModel }[] = [];
  for (const provider of providers) {
    if (provider.publicTextOnly && !task.publicText) continue;
    for (const model of provider.models) {
      if (model.tasks.includes(task.task)) out.push({ provider, model });
    }
  }
  return out;
}
