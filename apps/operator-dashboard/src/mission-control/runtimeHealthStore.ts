import type {
  MissionControlRuntimeHealth,
  MissionControlTimelineEvent,
} from "./types";

export interface RuntimeHealthStoreState {
  latest: MissionControlRuntimeHealth | null;
  timeline: MissionControlTimelineEvent[];
}

const MAX_TIMELINE_EVENTS = 500;

export class RuntimeHealthStore {
  private state: RuntimeHealthStoreState = {
    latest: null,
    timeline: [],
  };

  snapshot(): RuntimeHealthStoreState {
    return {
      latest: this.state.latest,
      timeline: [...this.state.timeline],
    };
  }

  updateHealth(health: MissionControlRuntimeHealth): void {
    this.state.latest = health;
  }

  appendEvent(event: MissionControlTimelineEvent): void {
    this.state.timeline.push(event);

    if (this.state.timeline.length > MAX_TIMELINE_EVENTS) {
      this.state.timeline.splice(
        0,
        this.state.timeline.length - MAX_TIMELINE_EVENTS,
      );
    }
  }
}

export const runtimeHealthStore = new RuntimeHealthStore();
