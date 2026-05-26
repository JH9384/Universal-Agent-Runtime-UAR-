import { create } from 'zustand';

export type RuntimeNode = {
  id: string;
  status: string;
};

export type TopologyState = {
  nodes: RuntimeNode[];
  setNodes: (nodes: RuntimeNode[]) => void;
};

export const useTopologyStore = create<TopologyState>((set) => ({
  nodes: [],
  setNodes: (nodes) => set({ nodes }),
}));
