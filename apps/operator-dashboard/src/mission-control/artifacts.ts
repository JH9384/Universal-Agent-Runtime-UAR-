export type ArtifactCategory =
  | "runtime-health"
  | "replay"
  | "topology"
  | "burnin"
  | "certification";

export interface ArtifactRecord {
  id: string;
  category: ArtifactCategory;
  createdAt: number;
  title: string;
  description?: string;
  tags: string[];
  replayLinked?: boolean;
}

export class ArtifactIndex {
  private artifacts: ArtifactRecord[] = [];

  add(record: ArtifactRecord): void {
    this.artifacts.push(record);
  }

  list(category?: ArtifactCategory): ArtifactRecord[] {
    if (!category) {
      return [...this.artifacts];
    }

    return this.artifacts.filter(
      (artifact) => artifact.category === category,
    );
  }
}

export const artifactIndex = new ArtifactIndex();
