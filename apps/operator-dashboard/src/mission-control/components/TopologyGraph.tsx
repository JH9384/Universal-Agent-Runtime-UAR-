import type { TopologySnapshot } from "../topology";

export interface TopologyGraphProps {
  snapshot: TopologySnapshot;
}

export function TopologyGraph({ snapshot }: TopologyGraphProps) {
  return (
    <section aria-label="Topology graph" className="mission-panel">
      <header>
        <h2>Topology</h2>
        <span>
          {snapshot.nodes.length} nodes / {snapshot.edges.length} edges
        </span>
      </header>

      <ul>
        {snapshot.nodes.map((node) => (
          <li key={node.id}>
            {node.kind} :: {node.id}
            {node.isolated ? " (isolated)" : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}
