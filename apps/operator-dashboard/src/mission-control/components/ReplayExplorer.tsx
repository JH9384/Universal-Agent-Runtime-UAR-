export interface ReplayExplorerProps {
  replayConfidence: number;
  divergence: number;
}

const percent = (value: number): string => `${Math.round(value * 100)}%`;

export function ReplayExplorer({
  replayConfidence,
  divergence,
}: ReplayExplorerProps) {
  return (
    <section aria-label="Replay explorer" className="mission-panel">
      <header>
        <h2>Replay Explorer</h2>
      </header>

      <dl>
        <div>
          <dt>Replay Confidence</dt>
          <dd>{percent(replayConfidence)}</dd>
        </div>
        <div>
          <dt>Divergence</dt>
          <dd>{percent(divergence)}</dd>
        </div>
      </dl>
    </section>
  );
}
