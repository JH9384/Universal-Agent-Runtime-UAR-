import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface TopologyNode {
  id: string;
  kind: string;
  isolated: boolean;
}

export function TopologyGraph() {
  const [nodes, setNodes] = useState<TopologyNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = () => {
      api
        .circuitBreakers()
        .then((data) => {
          if (!mounted) return;
          const mapped: TopologyNode[] = Object.entries(
            data.circuits || {}
          ).map(([name, info]) => ({
            id: name,
            kind: info.state || "unknown",
            isolated: info.state === "open",
          }));
          setNodes(mapped);
          setError(null);
        })
        .catch((err) => {
          if (!mounted) return;
          setError(String(err));
        })
        .finally(() => {
          if (mounted) setLoading(false);
        });
    };
    fetchData();
    const id = setInterval(fetchData, 5000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  if (loading) {
    return (
      <section aria-label="Topology graph" className="mission-panel">
        <header>
          <h2>Topology</h2>
        </header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Topology graph" className="mission-panel">
        <header>
          <h2>Topology</h2>
        </header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Topology graph" className="mission-panel">
      <header>
        <h2>Topology</h2>
        <span>{nodes.length} nodes</span>
      </header>

      <ul>
        {nodes.map((node) => (
          <li key={node.id}>
            {node.kind} :: {node.id}
            {node.isolated ? " (isolated)" : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}
