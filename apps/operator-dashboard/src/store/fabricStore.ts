import { create } from 'zustand';

export type FabricState = {
  overallScore: number;
  anomalyCount: number;
  setHealth: (score: number, anomalies: number) => void;
};

export const useFabricStore = create<FabricState>((set) => ({
  overallScore: 0,
  anomalyCount: 0,
  setHealth: (score, anomalies) =>
    set({ overallScore: score, anomalyCount: anomalies }),
}));
