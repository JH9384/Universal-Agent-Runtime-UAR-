import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface CircuitEntry {
  name: string;
  state: string;
  failures: number;
}

const STATE_COLOR: Record<string, string> = {
  closed: "#22c55e",
  open: "#ef4444",
  half_open: "#f59e0b",
};

export function TopologyGraph() {
  const [circuits, setCircuits] = useState<CircuitEntry[]>([]);
  const [resetting, setResetting] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load() {
    return api
      .circuitBreakers()
      .then((data) => {
        const mapped: CircuitEntry[] = Object.entries(data.circuits || {}).map(
          ([name, info]) => ({
            name,
            state: info.state ?? "unknown",
            failures: info.failures ?? 0,
          })
        );
        setCircuits(mapped);
        setError(null);
      })
      .catch((err) => setError(String(err)));
  }

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    load().finally(() => { if (mounted) setLoading(false); });
    const id = setInterval(load, 5000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  function handleReset(name: string) {
    setResetting(name);
    api
      .resetCircuitBreaker(name)
      .then(load)
      .finally(() => setResetting(null));
  }

  const openCount = circuits.filter((c) => c.state === "open").length;

  if (loading) {
    return (
      <section aria-label="Topology graph" className="mission-panel">
        <header><h2>Topology</h2></header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Topology graph" className="mission-panel">
        <header><h2>Topology</h2></header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Topology graph" className="mission-panel">
      <header>
        <h2>Topology</h2>
        <span className={openCount > 0 ? "mc-status-summary--warn" : "mc-status-summary--ok"}>
          {openCount > 0 ? `${openCount} open` : "All closed"}
        </span>
      </header>

      <p className="mc-subtext">
        Circuit Breakers — {circuits.length} registered
      </p>

      <ul>
        {circuits.map((c) => {
          const color = STATE_COLOR[c.state] ?? "#94a3b8";
          return (
            <li key={c.name} className="mc-row mc-row--padded" style={{ "--mc-status-color": color } as React.CSSProperties}>
              <span className="mc-dot" />
              <span className="mc-subtext" style={{ "--mc-flex": "1", marginBottom: 0 } as React.CSSProperties}>{c.name}</span>
              <span className="mc-status-badge--xs">
                {c.state.replaceAll("_", "-")}
              </span>
              {c.failures > 0 && (
                <span className="mc-meta--warn">{c.failures}✗</span>
              )}
              {c.state === "open" && (
                <button
                  onClick={() => handleReset(c.name)}
                  disabled={resetting === c.name}
                  title="Reset circuit breaker"
                  className="mc-reset-btn"
                >
                  {resetting === c.name ? "…" : "Reset"}
                </button>
              )}
            </li>
          );
        })}
        {circuits.length === 0 && (
          <li className="mc-meta--muted">No circuit breakers registered.</li>
        )}
      </ul>
    </section>
  );
}
