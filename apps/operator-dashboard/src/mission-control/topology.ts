export interface TopologyNode {
  id: string;
  kind:
    | "runtime"
    | "queue"
    | "websocket"
    | "replay"
    | "observer"
    | "scheduler";
  pressure?: number;
  isolated?: boolean;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  fanout?: number;
  congested?: boolean;
}

export interface TopologySnapshot {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  generatedAt: number;
}

export function topologyHealth(snapshot: TopologySnapshot): boolean {
  return !snapshot.nodes.some((node) => node.isolated);
}
