import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { RunRecord } from "../../api/client";

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  running: "#3b82f6",
  failed: "#ef4444",
  pending: "#f59e0b",
};

export function ReplayExplorer() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [filter, setFilter] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = () => {
      api
        .listRuns()
        .then((data) => {
          if (!mounted) return;
          setRuns(data.slice(0, 50));
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
    const id = setInterval(fetchData, 10_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  function copyId(id: string) {
    navigator.clipboard.writeText(id).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(null), 1500);
    }).catch(() => {
      setCopied(null);
    });
  }

  const visible = filter.trim()
    ? runs.filter(
        (r) =>
          r.run_id.includes(filter.trim()) ||
          r.status.includes(filter.trim())
      )
    : runs;

  if (loading) {
    return (
      <section aria-label="Replay explorer" className="mission-panel">
        <header><h2>Replay Explorer</h2></header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Replay explorer" className="mission-panel">
        <header><h2>Replay Explorer</h2></header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Replay explorer" className="mission-panel">
      <header>
        <h2>Replay Explorer</h2>
        <span>{visible.length} / {runs.length} runs</span>
      </header>

      <input
        type="search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter by run ID or status…"
        className="mc-search-input"
      />

      <ul>
        {visible.map((r) => {
          const color = STATUS_COLOR[r.status] ?? "#94a3b8";
          return (
            <li key={r.run_id} className="mc-row" style={{ "--mc-status-color": color } as React.CSSProperties}>
              <span className="mc-dot" />
              <code className="mc-run-id">{r.run_id}</code>
              <span className="mc-status-badge">
                {r.status}
              </span>
              {r.skills && r.skills.length > 0 && (
                <span className="mc-skill-count">
                  {r.skills.length} skills
                </span>
              )}
              <button
                onClick={() => copyId(r.run_id)}
                title="Copy run ID"
                className={copied === r.run_id ? "mc-copy-btn mc-copy-btn--copied" : "mc-copy-btn"}
              >
                {copied === r.run_id ? "✓" : "⧉"}
              </button>
            </li>
          );
        })}
        {visible.length === 0 && (
          <li className="mc-meta--muted">
            {filter ? "No matching runs." : "No runs yet."}
          </li>
        )}
      </ul>
    </section>
  );
}
