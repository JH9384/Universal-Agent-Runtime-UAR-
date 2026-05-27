import { useEffect } from 'react';

import { RuntimeWebSocketBridge } from '../runtime/websocket';
import { RuntimeEventRouter } from '../runtime/eventRouter';

export function useFabricStream(
  url: string,
  router: RuntimeEventRouter,
): void {
  useEffect(() => {
    const bridge = new RuntimeWebSocketBridge();

    bridge.connect(url, (payload) => {
      if (typeof payload === 'object' && payload !== null) {
        router.route(payload as never);
      }
    });

    return () => bridge.disconnect();
  }, [url, router]);
}
