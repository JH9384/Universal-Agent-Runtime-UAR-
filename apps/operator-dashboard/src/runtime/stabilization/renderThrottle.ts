export type RenderPriority = "low" | "normal" | "high";

export interface RenderThrottleOptions {
  /** Target maximum render cadence in frames per second. */
  maxFps?: number;
  /** Maximum callbacks allowed to wait before forced flush. */
  maxBufferedCallbacks?: number;
  /** If true, high-priority callbacks bypass cadence delay. */
  allowHighPriorityBypass?: boolean;
}

export interface ScheduledRender {
  id: number;
  priority: RenderPriority;
  enqueuedAt: number;
  cancel: () => void;
}

type RenderCallback = () => void;

interface QueueItem {
  id: number;
  callback: RenderCallback;
  priority: RenderPriority;
  enqueuedAt: number;
  cancelled: boolean;
}

const DEFAULT_MAX_FPS = 30;
const DEFAULT_MAX_BUFFERED_CALLBACKS = 250;

const now = (): number =>
  typeof performance !== "undefined" && typeof performance.now === "function"
    ? performance.now()
    : Date.now();

const nextFrame = (callback: () => void): number => {
  if (typeof requestAnimationFrame === "function") {
    return requestAnimationFrame(callback);
  }

  return setTimeout(callback, 16) as unknown as number;
};

const cancelFrame = (handle: number): void => {
  if (typeof cancelAnimationFrame === "function") {
    cancelAnimationFrame(handle);
    return;
  }

  clearTimeout(handle as unknown as ReturnType<typeof setTimeout>);
};

/**
 * Batches dashboard render callbacks so observer/UI pressure cannot amplify
 * runtime event pressure into a render storm.
 */
export class RenderThrottle {
  private readonly minFrameMs: number;
  private readonly maxBufferedCallbacks: number;
  private readonly allowHighPriorityBypass: boolean;
  private queue: QueueItem[] = [];
  private frameHandle: number | null = null;
  private lastFlushAt = 0;
  private nextId = 1;

  constructor(options: RenderThrottleOptions = {}) {
    const maxFps = Math.max(1, options.maxFps ?? DEFAULT_MAX_FPS);
    this.minFrameMs = 1000 / maxFps;
    this.maxBufferedCallbacks = Math.max(
      1,
      options.maxBufferedCallbacks ?? DEFAULT_MAX_BUFFERED_CALLBACKS,
    );
    this.allowHighPriorityBypass = options.allowHighPriorityBypass ?? true;
  }

  schedule(
    callback: RenderCallback,
    priority: RenderPriority = "normal",
  ): ScheduledRender {
    const item: QueueItem = {
      id: this.nextId++,
      callback,
      priority,
      enqueuedAt: now(),
      cancelled: false,
    };

    this.queue.push(item);
    this.trimOverflow();

    if (this.allowHighPriorityBypass && priority === "high") {
      this.flushSoon(true);
    } else {
      this.flushSoon(false);
    }

    return {
      id: item.id,
      priority,
      enqueuedAt: item.enqueuedAt,
      cancel: () => {
        item.cancelled = true;
      },
    };
  }

  flush(): number {
    if (this.frameHandle !== null) {
      cancelFrame(this.frameHandle);
      this.frameHandle = null;
    }

    const pending = this.queue;
    this.queue = [];
    this.lastFlushAt = now();

    const ordered = pending
      .filter((item) => !item.cancelled)
      .sort((a, b) => priorityWeight(b.priority) - priorityWeight(a.priority));

    for (const item of ordered) {
      item.callback();
    }

    return ordered.length;
  }

  clear(): void {
    if (this.frameHandle !== null) {
      cancelFrame(this.frameHandle);
      this.frameHandle = null;
    }
    this.queue = [];
  }

  pressure(): number {
    return this.queue.length / this.maxBufferedCallbacks;
  }

  pending(): number {
    return this.queue.filter((item) => !item.cancelled).length;
  }

  private flushSoon(force: boolean): void {
    if (this.frameHandle !== null) {
      return;
    }

    const elapsed = now() - this.lastFlushAt;
    if (force || elapsed >= this.minFrameMs) {
      this.frameHandle = nextFrame(() => this.flush());
      return;
    }

    const delay = Math.max(0, this.minFrameMs - elapsed);
    this.frameHandle = setTimeout(() => this.flush(), delay) as unknown as number;
  }

  private trimOverflow(): void {
    if (this.queue.length <= this.maxBufferedCallbacks) {
      return;
    }

    const highPriority = this.queue.filter((item) => item.priority === "high");
    const rest = this.queue.filter((item) => item.priority !== "high");
    const keepRest = rest.slice(
      Math.max(0, rest.length - (this.maxBufferedCallbacks - highPriority.length)),
    );

    this.queue = [...highPriority, ...keepRest].slice(-this.maxBufferedCallbacks);
  }
}

const priorityWeight = (priority: RenderPriority): number => {
  switch (priority) {
    case "high":
      return 3;
    case "normal":
      return 2;
    case "low":
      return 1;
    default:
      return 0;
  }
};

export const dashboardRenderThrottle = new RenderThrottle();
