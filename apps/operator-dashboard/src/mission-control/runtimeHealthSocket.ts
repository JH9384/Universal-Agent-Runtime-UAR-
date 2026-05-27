import { runtimeHealthEmitter } from "../runtime/telemetry/runtimeHealthEmitter";
import type { RuntimeHealthPayload } from "../runtime/telemetry/runtimeHealthEmitter";
import { runtimeHealthStore } from "./runtimeHealthStore";

const toMissionHealth = (payload: RuntimeHealthPayload) => ({
  pressure: payload.pressure,
  oscillation: payload.oscillation,
  replayConfidence: payload.replay_confidence,
  starvation: payload.starvation,
  mode: payload.mode,
  healthy: payload.healthy,
  emittedAt: payload.emitted_at,
});

export function attachRuntimeHealthSocket(url: string): () => void {
  const socket = new WebSocket(url);

  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data) as RuntimeHealthPayload;
    const emitted = runtimeHealthEmitter.emit(payload);

    if (emitted) {
      runtimeHealthStore.updateHealth(toMissionHealth(payload));
    }
  };

  return () => socket.close();
}
