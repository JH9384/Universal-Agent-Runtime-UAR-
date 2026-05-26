import { create } from 'zustand';

export type RuntimeAnomaly = {
  id: string;
  severity: string;
};

export type AnomalyState = {
  anomalies: RuntimeAnomaly[];
  setAnomalies: (anomalies: RuntimeAnomaly[]) => void;
};

export const useAnomalyStore = create<AnomalyState>((set) => ({
  anomalies: [],
  setAnomalies: (anomalies) => set({ anomalies }),
}));
