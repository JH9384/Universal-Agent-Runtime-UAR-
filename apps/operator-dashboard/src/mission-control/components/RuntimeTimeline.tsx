import { useEffect, useState } from "react";
import type { MissionControlTimelineEvent } from "../types";
import { api } from "../../api/client";

export function RuntimeTimeline() {
  const [events, setEvents] = useState<MissionControlTimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = () => {
      api
        .listRuns()
        .then((runs) => {
          if (!mounted) return;
          const mapped: MissionControlTimelineEvent[] = runs
            .slice(0, 20)
            .map((r, i) => ({
              id: r.run_id || String(i),
              title: `Run ${(r.run_id || "").slice(0, 8)} — ${r.status}`,
              kind: "burnin-artifact",
              severity: r.status === "completed" ? "info" : "warning",
              occurredAt: r.created_at || r.timestamp || Date.now(),
            }));
          setEvents(mapped);
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
        <header>
          <h2>Runtime Timeline</h2>
        </header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Runtime timeline" className="mission-panel">
        <header>
          <h2>Runtime Timeline</h2>
        </header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Runtime timeline" className="mission-panel">
      <header>
        <h2>Runtime Timeline</h2>
        <span>{events.length} events</span>
      </header>

      <ul>
        {events.map((event) => (
          <li key={event.id}>
            <strong>{event.title}</strong>
            <div>{event.kind}</div>
            <div>{event.severity}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
