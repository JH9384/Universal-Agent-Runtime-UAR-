export interface MutationBatch<T> {
  items: T[];
  createdAt: number;
}

export class MutationBatcher<T> {
  private current: MutationBatch<T> = {
    items: [],
    createdAt: Date.now(),
  };

  constructor(
    private readonly maxBatchSize: number = 128,
  ) {}

  add(item: T): MutationBatch<T> | null {
    this.current.items.push(item);

    if (this.current.items.length >= this.maxBatchSize) {
      return this.flush();
    }

    return null;
  }

  flush(): MutationBatch<T> {
    const completed = this.current;

    this.current = {
      items: [],
      createdAt: Date.now(),
    };

    return completed;
  }
}
