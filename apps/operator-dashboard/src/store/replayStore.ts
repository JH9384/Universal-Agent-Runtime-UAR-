import { create } from 'zustand';

export type ReplayEvent = {
  id: string;
  timestamp: number;
  state: string;
};

export type ReplayState = {
  events: ReplayEvent[];
  pushReplay: (event: ReplayEvent) => void;
};

export const useReplayStore = create<ReplayState>((set) => ({
  events: [],
  pushReplay: (event) =>
    set((state) => ({ events: [...state.events, event] })),
}));
