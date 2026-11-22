"use client";

import { Component, createElement, lazy, Suspense, useState, type ComponentType, type ReactNode } from "react";

import { MapRetry } from "@/components/map/MapRetry";

export const BLOCK_FAILED = "This figure could not be loaded. Try again in a moment.";

type Caught = { failed: boolean };

export class BlockBoundary extends Component<{ children: ReactNode; onRetry: () => void }, Caught> {
  state: Caught = { failed: false };

  static getDerivedStateFromError(): Caught {
    return { failed: true };
  }

  componentDidCatch(cause: unknown) {
    console.error(cause);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return <MapRetry message={BLOCK_FAILED} onRetry={this.props.onRetry} />;
  }
}

export type RetryableLazy<P extends object> = { current: () => ComponentType<P>; retry: (failed: ComponentType<P>) => ComponentType<P> };

export function retryableLazy<P extends object>(load: () => Promise<ComponentType<P>>): RetryableLazy<P> {
  const fresh = (): ComponentType<P> => lazy(() => load().then((component) => ({ default: component }))) as unknown as ComponentType<P>;
  let shared = fresh();
  return {
    current: () => shared,
    retry(failed) {
      if (failed === shared) shared = fresh();
      return shared;
    }
  };
}

export function lazyBlock<P extends object>(load: () => Promise<ComponentType<P>>, placeholder: ReactNode): ComponentType<P> {
  const loader = retryableLazy(load);
  function LazyBlock(props: P) {
    const [drawn, setDrawn] = useState(() => ({ round: 0, Lazy: loader.current() }));
    const retry = () => setDrawn({ round: drawn.round + 1, Lazy: loader.retry(drawn.Lazy) });
    return (
      <BlockBoundary key={drawn.round} onRetry={retry}>
        <Suspense fallback={placeholder}>{createElement(drawn.Lazy, props)}</Suspense>
      </BlockBoundary>
    );
  }
  return LazyBlock;
}
