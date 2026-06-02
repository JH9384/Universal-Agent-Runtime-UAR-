import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { RunRecord } from "../../api/client";

type StatusFilter = "all" | "completed" | "failed" | "running" | "pending";

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  running: "#3b82f6",
  failed: "#ef4444",
  pending: "#f59e0b",
};

export function ArtifactBrowser() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = () => {
      api
        .listRuns()
        .then((data) => {
          if (!mounted) return;
          setRuns(data);
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

  const visible = filter === "all" ? runs : runs.filter((r) => r.status === filter);

  const counts = runs.reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] ?? 0) + 1;
    return acc;
  }, {});

  if (loading) {
    return (
      <section aria-label="Artifact browser" className="mission-panel">
        <header><h2>Artifacts</h2></header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Artifact browser" className="mission-panel">
        <header><h2>Artifacts</h2></header>
        <p className="error">{error}</p>
      </section>
    );
  }

  const FILTERS: StatusFilter[] = ["all", "completed", "failed", "running", "pending"];

  return (
    <section aria-label="Artifact browser" className="mission-panel">
      <header>
        <h2>Artifacts</h2>
        <span>{visible.length} / {runs.length} records</span>
      </header>

      <div className="mc-filter-bar">
        {FILTERS.map((f) => {
          const active = filter === f;
          const color = f === "all" ? "#66fcf1" : (STATUS_COLOR[f] ?? "#94a3b8");
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={active ? "mc-filter-btn mc-filter-btn--active" : "mc-filter-btn"}
              style={{
                "--mc-color": active ? "#0b0c10" : color,
                "--mc-bg": active ? color : "#0b0c10",
                "--mc-border": active ? color : "#1f2833",
              } as import("react").CSSProperties}
              aria-pressed={active ? "true" : "false"}
            >
              {f}{f !== "all" && counts[f] ? ` (${counts[f]})` : f === "all" ? ` (${runs.length})` : ""}
            </button>
          );
        })}
      </div>

      <ul>
        {visible.map((r) => {
          const color = STATUS_COLOR[r.status] ?? "#94a3b8";
          return (
            <li key={r.run_id} style={{ "--mc-status-color": color } as import("react").CSSProperties}>
              <div className="mc-row mc-row--sm-gap">
                <span className="mc-dot mc-dot--sm" />
                <code className="mc-run-id">{r.run_id}</code>
                <span className="mc-status-badge">{r.status}</span>
              </div>
              {r.skills && r.skills.length > 0 && (
                <div className="mc-skills">{r.skills.join(", ")}</div>
              )}
            </li>
          );
        })}
        {visible.length === 0 && (
          <li className="mc-meta--muted">No records match this filter.</li>
        )}
      </ul>
    </section>
  );
}
