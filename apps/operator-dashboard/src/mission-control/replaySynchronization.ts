export interface ReplaySynchronizationState {
  replayConfidence: number;
  divergence: number;
  synchronized: boolean;
  updatedAt: number;
}

export function replaySynchronized(
  state: ReplaySynchronizationState,
): boolean {
  return (
    state.synchronized &&
    state.replayConfidence >= 0.99 &&
    state.divergence <= 0.01
  );
}
