import { RuntimeHealthPanel } from "./mission-control/components/RuntimeHealthPanel";
import { RuntimeTimeline } from "./mission-control/components/RuntimeTimeline";
import { ReplayExplorer } from "./mission-control/components/ReplayExplorer";
import { ArtifactBrowser } from "./mission-control/components/ArtifactBrowser";
import { TopologyGraph } from "./mission-control/components/TopologyGraph";

export function App() {
  return (
    <div className="mission-control">
      <header className="mc-header">
        <h1>UAR Mission Control</h1>
        <span className="mc-version">v1.0.0</span>
      </header>
      <main className="mc-grid">
        <RuntimeHealthPanel />
        <TopologyGraph />
        <RuntimeTimeline />
        <ReplayExplorer />
        <ArtifactBrowser />
      </main>
    </div>
  );
}
