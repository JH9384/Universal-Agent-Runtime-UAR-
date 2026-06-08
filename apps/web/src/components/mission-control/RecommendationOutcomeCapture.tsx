import { useState } from "react";
import { authHeaders } from "../../utils/auth";

type OutcomeType = "resolved" | "recurred" | "unknown";

interface RecommendationOutcomeCaptureProps {
  recommendationIds: string[];
  runId?: string | null;
  onRecorded?: () => void;
}

async function postOutcome(recommendationId: string, outcomeType: OutcomeType, runId?: string | null) {
  const response = await fetch(`${window.location.origin}/api/uar/recommendations/outcome`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      recommendation_id: recommendationId,
      outcome_type: outcomeType,
      run_id: runId ?? undefined,
      source: "operator_briefing",
    }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${text}`);
  }

  return response.json();
}

export function RecommendationOutcomeCapture({ recommendationIds, runId, onRecorded }: RecommendationOutcomeCaptureProps) {
  const [selectedId, setSelectedId] = useState(recommendationIds[0] ?? "");
  const [submitting, setSubmitting] = useState<OutcomeType | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (recommendationIds.length === 0) return null;

  async function record(outcomeType: OutcomeType) {
    if (!selectedId) return;
    setSubmitting(outcomeType);
    setMessage(null);
    setError(null);
    try {
      await postOutcome(selectedId, outcomeType, runId);
      setMessage(`Recorded ${outcomeType} for ${selectedId}`);
      onRecorded?.();
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="mc-briefing-section">
      <h3>Record outcome</h3>
      <p className="mc-subtext">
        Reuses the existing recommendation outcome path. No fleet-specific outcome table.
      </p>
      <label className="mc-field-label" htmlFor="recommendation-outcome-id">
        Recommendation
      </label>
      <select
        id="recommendation-outcome-id"
        className="mc-select"
        value={selectedId}
        onChange={(e) => setSelectedId(e.target.value)}
      >
        {recommendationIds.map((id) => (
          <option key={id} value={id}>{id}</option>
        ))}
      </select>
      <div className="mc-briefing-links">
        <button type="button" className="mc-filter-btn" disabled={submitting !== null} onClick={() => record("resolved")}>
          {submitting === "resolved" ? "Recording…" : "Resolved"}
        </button>
        <button type="button" className="mc-filter-btn" disabled={submitting !== null} onClick={() => record("recurred")}>
          {submitting === "recurred" ? "Recording…" : "Recurred"}
        </button>
        <button type="button" className="mc-filter-btn" disabled={submitting !== null} onClick={() => record("unknown")}>
          {submitting === "unknown" ? "Recording…" : "Unknown"}
        </button>
      </div>
      {message && <p className="mc-status-summary--ok">{message}</p>}
      {error && <p className="mc-status-summary--warn">{error}</p>}
    </div>
  );
}
