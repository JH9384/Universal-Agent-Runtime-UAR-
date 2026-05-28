import { useEffect, useState } from "react";
import { api } from "../../api/client";

export interface ArtifactRecord {
  id: string;
  title: string;
  category: string;
}

export function ArtifactBrowser() {
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = () => {
      api
        .listRuns()
        .then((runs) => {
          if (!mounted) return;
          const mapped: ArtifactRecord[] = runs.map((r) => ({
            id: r.run_id,
            title: `Run ${r.run_id.slice(0, 8)}`,
            category: r.status || "unknown",
          }));
          setArtifacts(mapped);
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
      <section aria-label="Artifact browser" className="mission-panel">
        <header>
          <h2>Artifacts</h2>
        </header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Artifact browser" className="mission-panel">
        <header>
          <h2>Artifacts</h2>
        </header>
        <p className="error">{error}</p>
      </section>
    );
  }

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
