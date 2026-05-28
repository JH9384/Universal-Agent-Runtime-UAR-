import { useEffect, useState } from "react";
import { api } from "../../api/client";

export function ReplayExplorer() {
  const [runs, setRuns] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = () => {
      api
        .listRuns()
        .then((data) => {
          if (!mounted) return;
          const ids = data.map((r) => r.run_id).slice(0, 10);
          setRuns(ids);
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
      <section aria-label="Replay explorer" className="mission-panel">
        <header>
          <h2>Replay Explorer</h2>
        </header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Replay explorer" className="mission-panel">
        <header>
          <h2>Replay Explorer</h2>
        </header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Replay explorer" className="mission-panel">
      <header>
        <h2>Replay Explorer</h2>
        <span>{runs.length} recent runs</span>
      </header>

      <ul>
        {runs.map((runId) => (
          <li key={runId}>{runId}</li>
        ))}
      </ul>
    </section>
  );
}
