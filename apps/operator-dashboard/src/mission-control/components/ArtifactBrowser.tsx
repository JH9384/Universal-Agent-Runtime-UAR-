import type { ArtifactRecord } from "../artifacts";

export interface ArtifactBrowserProps {
  artifacts: ArtifactRecord[];
}

export function ArtifactBrowser({ artifacts }: ArtifactBrowserProps) {
  return (
    <section aria-label="Artifact browser" className="mission-panel">
      <header>
        <h2>Artifacts</h2>
        <span>{artifacts.length} records</span>
      </header>

      <ul>
        {artifacts.map((artifact) => (
          <li key={artifact.id}>
            <strong>{artifact.title}</strong>
            <div>{artifact.category}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
