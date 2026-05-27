export interface RuntimeHealthPayload {
  pressure: number;
  oscillation: number;
  replay_confidence: number;
  starvation: boolean;
  mode: string;
  healthy: boolean;
  emitted_at: number;
}

export type RuntimeHealthListener = (
  payload: RuntimeHealthPayload,
) => void;

export class RuntimeHealthEmitter {
  private listeners = new Set<RuntimeHealthListener>();
  private lastEmit = 0;

  constructor(private readonly cadenceMs = 250) {}

  subscribe(listener: RuntimeHealthListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit(payload: RuntimeHealthPayload): boolean {
    const now = Date.now();
    if (now - this.lastEmit < this.cadenceMs) {
      return false;
    }

    this.lastEmit = now;

    for (const listener of this.listeners) {
      listener(payload);
    }

    return true;
  }
}

export const runtimeHealthEmitter = new RuntimeHealthEmitter();
