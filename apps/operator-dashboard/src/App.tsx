import { useState } from "react";
import pkg from "../package.json";
import { RuntimeHealthPanel } from "./mission-control/components/RuntimeHealthPanel";
import { RuntimeTimeline } from "./mission-control/components/RuntimeTimeline";
import { ReplayExplorer } from "./mission-control/components/ReplayExplorer";
import { ArtifactBrowser } from "./mission-control/components/ArtifactBrowser";
import { TopologyGraph } from "./mission-control/components/TopologyGraph";

type Tab = "health" | "topology" | "replay" | "artifacts";

const TABS: { id: Tab; label: string }[] = [
  { id: "health", label: "Health" },
  { id: "topology", label: "Topology" },
  { id: "replay", label: "Replay" },
  { id: "artifacts", label: "Artifacts" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("health");

  return (
    <div className="mission-control">
      <header className="mc-header">
        <h1>UAR Mission Control</h1>
        <nav className="mc-tabs" role="tablist" aria-label="Mission Control sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id ? "true" : "false"}
              className={`mc-tab${tab === t.id ? " mc-tab--active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <span className="mc-version">v{pkg.version}</span>
      </header>

      <main className="mc-tab-content" role="tabpanel">
        {tab === "health" && (
          <div className="mc-grid mc-grid--health">
            <RuntimeHealthPanel />
            <div className="mc-timeline-col">
              <RuntimeTimeline />
            </div>
          </div>
        )}
        {tab === "topology" && (
          <div className="mc-grid">
            <TopologyGraph />
          </div>
        )}
        {tab === "replay" && (
          <div className="mc-grid mc-grid--wide">
            <ReplayExplorer />
          </div>
        )}
        {tab === "artifacts" && (
          <div className="mc-grid">
            <ArtifactBrowser />
          </div>
        )}
      </main>
    </div>
  );
}
