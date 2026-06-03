export type MissionControlPanelId =
  | "runtime-health"
  | "runtime-timeline"
  | "replay-explorer"
  | "artifact-browser"
  | "topology"
  | "certification";

export interface MissionControlPanelState {
  id: MissionControlPanelId;
  title: string;
  enabled: boolean;
  priority: number;
}

export interface MissionControlRuntimeHealth {
  pressure: number;
  oscillation: number;
  replayConfidence: number;
  starvation: boolean;
  mode: string;
  healthy: boolean;
  emittedAt: number;
}

export interface MissionControlTimelineEvent {
  id: string;
  kind:
    | "mode-change"
    | "pressure-spike"
    | "replay-divergence"
    | "starvation"
    | "topology-partition"
    | "burnin-artifact";
  severity: "info" | "warning" | "critical";
  occurredAt: number;
  title: string;
  detail?: string;
}
