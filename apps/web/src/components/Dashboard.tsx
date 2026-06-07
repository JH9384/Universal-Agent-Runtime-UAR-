import { useState } from "react";
import pkg from "../../package.json";
import { RuntimeHealthPanel } from "./mission-control/RuntimeHealthPanel";
import { RuntimeTimeline } from "./mission-control/RuntimeTimeline";
import { ReplayExplorer } from "./mission-control/ReplayExplorer";
import { ArtifactBrowser } from "./mission-control/ArtifactBrowser";
import { TopologyGraph } from "./mission-control/TopologyGraph";
import { OperatorBriefingPanel } from "./mission-control/OperatorBriefingPanel";
import { FocusModePanel } from "./mission-control/FocusModePanel";
import "./Dashboard.css";

type Tab = "briefing" | "focus" | "health" | "topology" | "replay" | "artifacts";

const TABS: { id: Tab; label: string }[] = [
  { id: "briefing", label: "Briefing" },
  { id: "focus", label: "Focus" },
  { id: "health", label: "Health" },
  { id: "topology", label: "Topology" },
  { id: "replay", label: "Replay" },
  { id: "artifacts", label: "Artifacts" },
];

interface DashboardProps {
  onBack?: () => void;
  onToggleMode?: () => void;
  modeLabel?: string;
}

export function Dashboard({ onBack, onToggleMode, modeLabel }: DashboardProps) {
  const [tab, setTab] = useState<Tab>("briefing");
  const [replayRunId, setReplayRunId] = useState<string | null>(null);

  const openReplay = (runId: string) => {
    setReplayRunId(runId);
    setTab("replay");
  };

  const selectOperationalTab = (nextTab: "health" | "topology" | "replay" | "artifacts") => {
    setTab(nextTab);
  };

  return (
    <div className="dashboard-root">
      <header className="mc-header">
        <h1>UAR Mission Control</h1>
        <nav className="mc-tabs" role="tablist" aria-label="Mission Control sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id ? "true" : "false"}
              className={tab === t.id ? "mc-tab mc-tab--active" : "mc-tab"}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <span className="mc-version">v{pkg.version}</span>
        {onToggleMode && (
          <button
            type="button"
            onClick={onToggleMode}
            className="mc-tab"
          >
            Toggle Mode
          </button>
        )}
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="mc-tab"
            style={{ marginLeft: "auto" }}
          >
            {modeLabel ?? "Back"}
          </button>
        )}
      </header>

      <main className="mc-tab-content" role="tabpanel">
        {tab === "briefing" && (
          <div className="mc-grid mc-grid--wide">
            <OperatorBriefingPanel onOpenReplay={openReplay} onSelectTab={selectOperationalTab} />
          </div>
        )}
        {tab === "focus" && (
          <div className="mc-grid mc-grid--wide">
            <FocusModePanel onOpenReplay={openReplay} onSelectTab={selectOperationalTab} />
          </div>
        )}
        {tab === "health" && (
          <div className="mc-grid--health">
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
            <ReplayExplorer initialRunId={replayRunId ?? undefined} />
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
