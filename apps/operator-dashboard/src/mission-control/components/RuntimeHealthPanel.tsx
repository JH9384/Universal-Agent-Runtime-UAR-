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
          const cbs = data.circuit_breakers || [];
          const skills = data.skills || [];
          const openCount = cbs.filter((cb) => cb.state === "open").length;
          const halfOpenCount = cbs.filter((cb) => cb.state === "half_open").length;
          const totalCbs = cbs.length || 1;
          const availableSkills = skills.filter((s) => s.available).length;
          const totalSkills = skills.length || 1;
          const pressure = openCount / totalCbs;
          const oscillation = halfOpenCount / totalCbs;
          const replayConfidence = availableSkills / totalSkills;
          const starvation = skills.length > 0 && availableSkills === 0;
          const healthy = openCount === 0 && !starvation;
          const mode = openCount > 0 ? "degraded" : halfOpenCount > 0 ? "recovering" : starvation ? "starved" : "healthy";
          setHealth({
            pressure,
            oscillation,
            replayConfidence,
            starvation,
            mode,
            healthy,
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
