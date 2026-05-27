export class RuntimeWebSocketBridge {
  private socket: WebSocket | null = null;

  connect(url: string, onMessage: (payload: unknown) => void): void {
    this.socket = new WebSocket(url);

    this.socket.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch {
        onMessage(event.data);
      }
    };
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
  }
}
