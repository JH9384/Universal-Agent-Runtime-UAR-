import { RuntimeEventRouter } from './eventRouter';
import { useTopologyStore } from '../store/topologyStore';

export function attachLiveTopologySync(router: RuntimeEventRouter): void {
  router.on('topology.update', (event) => {
    const payload = event.payload as {
      nodes?: { id: string; status: string }[];
      edges?: {
        source: string;
        target: string;
        label?: string;
        animated?: boolean;
      }[];
    };

    if (payload.nodes) {
      useTopologyStore.getState().setNodes(payload.nodes);
    }

    if (payload.edges) {
      useTopologyStore.getState().setEdges(payload.edges);
    }
  });
}
