import type { MissionControlTimelineEvent } from "./types";

export interface TimelineWindow {
  events: MissionControlTimelineEvent[];
  total: number;
}

export function timelineWindow(
  events: MissionControlTimelineEvent[],
  limit = 250,
): TimelineWindow {
  const bounded = events.slice(-limit);

  return {
    events: bounded,
    total: events.length,
  };
}
