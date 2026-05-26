export type RuntimeEvent = {
  event_type: string;
  payload: Record<string, unknown>;
};

export type RuntimeEventHandler = (event: RuntimeEvent) => void;

export class RuntimeEventRouter {
  private handlers: Record<string, RuntimeEventHandler[]> = {};

  on(eventType: string, handler: RuntimeEventHandler): void {
    this.handlers[eventType] = this.handlers[eventType] ?? [];
    this.handlers[eventType].push(handler);
  }

  route(event: RuntimeEvent): void {
    const handlers = this.handlers[event.event_type] ?? [];
    for (const handler of handlers) {
      handler(event);
    }
  }
}
