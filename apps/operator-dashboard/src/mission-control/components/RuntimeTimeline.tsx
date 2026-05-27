import type { MissionControlTimelineEvent } from "../types";

export interface RuntimeTimelineProps {
  events: MissionControlTimelineEvent[];
}

export function RuntimeTimeline({ events }: RuntimeTimelineProps) {
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
