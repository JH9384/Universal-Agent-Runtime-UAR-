import { RuntimeEventRouter } from './eventRouter';

export function startDemoRuntimeLoop(router: RuntimeEventRouter): void {
  setInterval(() => {
    router.route({
      event_type: 'topology.update',
      payload: {
        nodes: [
          {
            id: 'runtime-a',
            status: Math.random() > 0.5 ? 'healthy' : 'synchronizing',
          },
          {
            id: 'runtime-b',
            status: Math.random() > 0.5 ? 'restoring' : 'healthy',
          },
          {
            id: 'runtime-c',
            status: Math.random() > 0.5 ? 'repairing' : 'healthy',
          },
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
      },
    });
  }, 2500);
}
