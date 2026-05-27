export interface RenderThrottleState {
  lastFrameAt: number;
  pendingMutations: number;
}

export class RenderThrottle {
  constructor(
    private readonly maxFramesPerSecond: number = 30,
  ) {}

  private state: RenderThrottleState = {
    lastFrameAt: 0,
    pendingMutations: 0,
  };

  shouldRender(now: number = Date.now()): boolean {
    const minimumDelta = 1000 / this.maxFramesPerSecond;

    if (now - this.state.lastFrameAt >= minimumDelta) {
      this.state.lastFrameAt = now;
      this.state.pendingMutations = 0;
      return true;
    }

    this.state.pendingMutations += 1;
    return false;
  }

  snapshot(): RenderThrottleState {
    return {
      ...this.state,
    };
  }
}
