"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";

import { FieldBlock } from "@/components/FormControls";
import { useMoveFocus } from "@/components/hooks/useMoveFocus";
import { RecordNotice } from "@/components/records/RecordNotice";
import { RecordSection } from "@/components/records/RecordSection";
import { RouteList, type RouteListHandlers, type RouteNames } from "@/components/settings/RouteList";
import { RoutingOverview } from "@/components/settings/RoutingOverview";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/Dropdown";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import {
  fetchRouting,
  modelsForTask,
  routeKey,
  sameRoutes,
  saveTaskRoute,
  testTaskRoute,
  type RouteRow,
  type RoutingState,
  type TaskRoute
} from "@/lib/routing";
import { moveItem, movedText } from "@/lib/listOrder";

function useRoutingState() {
  const [state, setState] = useState<RoutingState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [task, setTask] = useState("");

  const load = useCallback(() => {
    setLoadError(null);
    fetchRouting()
      .then((next) => {
        setState(next);
        setTask((current) => (current && next.tasks.some((row) => row.task === current) ? current : (next.tasks[0]?.task ?? "")));
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Couldn't load the routing."));
  }, []);

  useEffect(load, [load]);

  const applyTask = useCallback((next: TaskRoute) => {
    setState((prev) => (prev ? { ...prev, tasks: prev.tasks.map((row) => (row.task === next.task ? next : row)) } : prev));
  }, []);

  return { state, loadError, load, task, setTask, applyTask };
}

function useRouteNames(state: RoutingState | null): RouteNames {
  return useMemo(
    () => ({
      provider: (row: RouteRow) => state?.providers.find((provider) => provider.id === row.provider)?.name ?? row.provider,
      model: (row: RouteRow) => state?.providers.find((provider) => provider.id === row.provider)?.models.find((model) => model.id === row.model)?.label ?? row.model
    }),
    [state]
  );
}

export function RoutingPanel() {
  const { toast } = useToast();
  const { state, loadError, load, task, setTask, applyTask } = useRoutingState();
  const names = useRouteNames(state);
  const current = useMemo(() => state?.tasks.find((row) => row.task === task) ?? null, [state, task]);
  const [draft, setDraft] = useState<RouteRow[]>([]);
  const [adding, setAdding] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const moveFocus = useMoveFocus(draft);

  useEffect(() => {
    setDraft(current ? current.routes : []);
    setAdding("");
    setError(null);
  }, [current]);

  const candidates = useMemo(() => {
    if (!state || !current) return [];
    const taken = new Set(draft.map(routeKey));
    return modelsForTask(state.providers, current)
      .filter(({ provider, model }) => !taken.has(routeKey({ provider: provider.id, model: model.id })))
      .map(({ provider, model }) => ({ value: `${provider.id}:${model.id}`, label: model.label, hint: provider.name, group: provider.name }));
  }, [current, draft, state]);

  function move(from: number, to: number) {
    if (to < 0 || to >= draft.length) return;
    const row = draft[from];
    setDraft((list) => moveItem(list, from, to));
    setAnnouncement(movedText(names.model(row), to, draft.length));
    moveFocus.followMove(routeKey(row), from, to, draft.length);
  }

  function add() {
    if (!adding || !state) return;
    const [provider, ...rest] = adding.split(":");
    const model = rest.join(":");
    const source = state.providers.find((row) => row.id === provider);
    if (!source) return;
    const row: RouteRow = { provider: source.id, model, enabled: true, keyState: source.keyState, testedAt: null, testError: null };
    setDraft((list) => [...list, row]);
    setAdding("");
    setAnnouncement(`${names.model(row)} added at position ${draft.length + 1}.`);
  }

  async function save() {
    if (!current) return;
    setSaving(true);
    setError(null);
    try {
      const next = await saveTaskRoute(current.task, draft.map(({ provider, model, enabled }) => ({ provider, model, enabled })));
      applyTask(next);
      toast({ title: next.normalisedNote ? "Saved with changes" : "Routing saved", description: next.normalisedNote ?? undefined, tone: next.normalisedNote ? "info" : "success" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the routing.");
    } finally {
      setSaving(false);
    }
  }

  async function test(row: RouteRow) {
    if (!current) return;
    const key = routeKey(row);
    setTesting(key);
    setError(null);
    try {
      const next = await testTaskRoute(current.task, row.provider, row.model);
      const verdict = next.routes.find((candidate) => routeKey(candidate) === key);
      setDraft((list) => list.map((item) => (routeKey(item) === key && verdict ? { ...item, keyState: verdict.keyState, testedAt: verdict.testedAt, testError: verdict.testError } : item)));
      const passed = verdict?.keyState === "PASSING";
      toast({ title: passed ? `${names.model(row)} answered` : `${names.model(row)} failed`, description: passed ? undefined : (verdict?.testError ?? undefined), tone: passed ? "success" : "error" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't run the test.");
    } finally {
      setTesting(null);
    }
  }

  if (!state) {
    return loadError ? (
      <RecordNotice tone="error" action={<Button variant="quiet" size="sm" onClick={load}>Try again</Button>}>
        {loadError}
      </RecordNotice>
    ) : (
      <Skeleton shape="lede" label="Reading the routing" />
    );
  }

  const dirty = current ? !sameRoutes(draft, current.routes) : false;
  const handlers: RouteListHandlers = {
    testing,
    onTest: (row) => void test(row),
    onMove: move,
    onRemove: (row) => setDraft((list) => list.filter((item) => routeKey(item) !== routeKey(row))),
    onEnable: (row, enabled) => setDraft((list) => list.map((item) => (routeKey(item) === routeKey(row) ? { ...item, enabled } : item))),
    register: moveFocus.register
  };

  return (
    <div className="grid gap-12">
      <RecordSection
        title={current?.label ?? "Routing"}
        description="Models are tried in this order. Switch one off to skip it without losing its place."
        aside={current && current.effectiveChain.length > 0 && !dirty ? <span data-testid="effective-chain">Now answering with <span className="text-ink-1">{current.effectiveChain.join(" → ")}</span></span> : null}
        testId="routing-panel"
      >
        <div className="max-w-md">
          <FieldBlock label="Task">
            <Dropdown value={task} onChange={setTask} options={state.tasks.map((row) => ({ value: row.task, label: row.label }))} searchable={false} advanceOnSelect={false} />
          </FieldBlock>
        </div>
        {draft.length === 0 ? <RecordNotice tone="warning">Add at least one model. A task with no model cannot answer.</RecordNotice> : <RouteList rows={draft} names={names} on={handlers} />}
        {candidates.length > 0 ? (
          <div className="grid max-w-xl gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
            <FieldBlock label="Add a model">
              <Dropdown value={adding} onChange={setAdding} options={candidates} placeholder="Choose a model" searchable advanceOnSelect={false} />
            </FieldBlock>
            <Button variant="quiet" disabled={!adding} onClick={add}>
              <Plus className="size-4" aria-hidden />
              Add
            </Button>
          </div>
        ) : null}
        <p aria-live="polite" className="sr-only">
          {announcement}
        </p>
        {error ? <RecordNotice tone="error">{error}</RecordNotice> : null}
        <ActionGroup align="start">
          {dirty ? (
            <Button variant="quiet" onClick={() => current && setDraft(current.routes)}>
              Reset
            </Button>
          ) : null}
          <Button variant="primary" busy={saving} busyLabel="Saving" disabled={!dirty || draft.length === 0} onClick={() => void save()}>
            Save order
          </Button>
        </ActionGroup>
      </RecordSection>
      <RoutingOverview tasks={state.tasks} />
    </div>
  );
}
