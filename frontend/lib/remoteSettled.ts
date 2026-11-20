export type RemoteFailure = { cause: unknown };

export type Settled<L, T> = { load: L | null; round: number; data: T | null; failure: RemoteFailure | null };

export const UNSETTLED: Settled<never, never> = { load: null, round: -1, data: null, failure: null };

export function settledFor<L, T>(settled: Settled<L, T>, load: L | null, round: number): Settled<L, T> {
  if (load === null || settled.load !== load || settled.round !== round) return UNSETTLED;
  return settled;
}
