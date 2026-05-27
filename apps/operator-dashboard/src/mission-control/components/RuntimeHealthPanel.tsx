import type { MissionControlRuntimeHealth } from "../types";

export interface RuntimeHealthPanelProps {
  health: MissionControlRuntimeHealth | null;
}

const percent = (value: number): string => `${Math.round(value * 100)}%`;

export function RuntimeHealthPanel({ health }: RuntimeHealthPanelProps) {
  if (!health) {
    return (
      <section aria-label="Runtime health" className="mission-panel">
        <h2>Runtime Health</h2>
        <p>No runtime health sample has been received yet.</p>
      </section>
    );
  }

  return (
    <section aria-label="Runtime health" className="mission-panel">
      <header>
        <h2>Runtime Health</h2>
        <strong>{health.healthy ? "Healthy" : "Attention"}</strong>
      </header>
      <dl>
        <div>
          <dt>Mode</dt>
          <dd>{health.mode}</dd>
        </div>
        <div>
          <dt>Pressure</dt>
          <dd>{percent(health.pressure)}</dd>
        </div>
        <div>
          <dt>Oscillation</dt>
          <dd>{percent(health.oscillation)}</dd>
        </div>
        <div>
          <dt>Replay Confidence</dt>
          <dd>{percent(health.replayConfidence)}</dd>
        </div>
        <div>
          <dt>Starvation</dt>
          <dd>{health.starvation ? "Detected" : "Clear"}</dd>
        </div>
      </dl>
    </section>
  );
}
