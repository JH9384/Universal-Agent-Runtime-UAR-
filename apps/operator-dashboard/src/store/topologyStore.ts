import { create } from 'zustand';

export type RuntimeNode = {
  id: string;
  status: string;
};

export type RuntimeEdge = {
  source: string;
  target: string;
  label?: string;
  animated?: boolean;
};

export type TopologyState = {
  nodes: RuntimeNode[];
  edges: RuntimeEdge[];
  setNodes: (nodes: RuntimeNode[]) => void;
  setEdges: (edges: RuntimeEdge[]) => void;
};

export const useTopologyStore = create<TopologyState>((set) => ({
  nodes: [
    { id: 'runtime-a', status: 'healthy' },
    { id: 'runtime-b', status: 'synchronizing' },
    { id: 'runtime-c', status: 'restoring' },
  ],
  edges: [
    {
      source: 'runtime-a',
      target: 'runtime-b',
      label: 'sync',
      animated: true,
    },
    {
      source: 'runtime-b',
      target: 'runtime-c',
      label: 'restore',
      animated: true,
    },
  ],
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
}));
