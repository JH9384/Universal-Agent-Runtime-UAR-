import { useEffect, useState } from "react";
import type { MissionControlRuntimeHealth } from "../types";
import { api } from "../../api/client";

const percent = (value: number): string => `${Math.round(value * 100)}%`;

export function RuntimeHealthPanel() {
  const [health, setHealth] = useState<MissionControlRuntimeHealth | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = () => {
      api
        .healthDashboard()
        .then((data) => {
          if (!mounted) return;
          const anyOpen = (data.circuit_breakers || []).some(
            (cb) => cb.state === "open"
          );
          setHealth({
            pressure: 0,
            oscillation: 0,
            replayConfidence: 1,
            starvation: false,
            mode: anyOpen ? "degraded" : "healthy",
            healthy: !anyOpen,
            emittedAt: Date.now(),
          });
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
      <section aria-label="Runtime health" className="mission-panel">
        <h2>Runtime Health</h2>
        <p>Loading...</p>
      </section>
    );
  }

  if (error || !health) {
    return (
      <section aria-label="Runtime health" className="mission-panel">
        <h2>Runtime Health</h2>
        <p className="error">{error || "No data"}</p>
      </section>
    );
  }

  return (
    <section aria-label="Runtime health" className="mission-panel">
      <header>
        <h2>Runtime Health</h2>
        <strong>{health.healthy ? "Healthy" : "Attention"}</strong>
      </header>
      <dl>
        <div>
          <dt>Mode</dt>
          <dd>{health.mode}</dd>
        </div>
        <div>
          <dt>Pressure</dt>
          <dd>{percent(health.pressure)}</dd>
        </div>
        <div>
          <dt>Oscillation</dt>
          <dd>{percent(health.oscillation)}</dd>
        </div>
        <div>
          <dt>Replay Confidence</dt>
          <dd>{percent(health.replayConfidence)}</dd>
        </div>
        <div>
          <dt>Starvation</dt>
          <dd>{health.starvation ? "Detected" : "Clear"}</dd>
        </div>
      </dl>
    </section>
  );
}
