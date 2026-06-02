import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { RunRecord } from "../../api/client";

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  running: "#3b82f6",
  failed: "#ef4444",
  pending: "#f59e0b",
};

function relativeTime(ts: number | undefined): string {
  if (!ts) return "—";
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export function RuntimeTimeline() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = () => {
      api
        .listRuns()
        .then((data) => {
          if (!mounted) return;
          setRuns(data.slice(0, 25));
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
      <section aria-label="Runtime timeline" className="mission-panel">
        <header><h2>Runtime Timeline</h2></header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Runtime timeline" className="mission-panel">
        <header><h2>Runtime Timeline</h2></header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Runtime timeline" className="mission-panel">
      <header>
        <h2>Runtime Timeline</h2>
        <span>{runs.length} runs</span>
      </header>
      <ul>
        {runs.map((r) => {
          const color = STATUS_COLOR[r.status] ?? "#94a3b8";
          const ts = r.created_at ?? r.timestamp;
          return (
            <li key={r.run_id} className="mc-row" style={{ "--mc-status-color": color } as React.CSSProperties}>
              <span className="mc-dot" />
              <code className="mc-run-id">
                {r.run_id.slice(0, 12)}
              </code>
              <span className="mc-status-badge">
                {r.status}
              </span>
              <span className="mc-meta">
                {relativeTime(ts)}
              </span>
            </li>
          );
        })}
        {runs.length === 0 && (
          <li className="mc-meta--muted">No runs yet.</li>
        )}
      </ul>
    </section>
  );
}
