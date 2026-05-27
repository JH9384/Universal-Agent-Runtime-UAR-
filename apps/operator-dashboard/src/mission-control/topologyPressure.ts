import type { TopologySnapshot } from "./topology";

export interface PressureZone {
  nodeId: string;
  pressure: number;
  congested: boolean;
}

export function computePressureZones(
  snapshot: TopologySnapshot,
): PressureZone[] {
  return snapshot.nodes.map((node) => ({
    nodeId: node.id,
    pressure: node.pressure ?? 0,
    congested: (node.pressure ?? 0) >= 0.75,
  }));
}
