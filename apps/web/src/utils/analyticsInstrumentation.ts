/**
 * RE-AUDIT SPRINT Ω-1 — Track 3: UX Reality Check
 *
 * Lightweight in-memory instrumentation for the evidence path:
 * Panel → Replay Button → Replay Explorer
 *
 * Events:
 *   replay_clicked   — operator clicked ▶ Replay
 *   replay_loaded    — ReplayExplorer mounted
 *   replay_completed — ReplayExplorer closed after >3s viewing
 *
 * KPIs:
 *   completionRate   = replay_loaded / replay_clicked
 *   medianTimeMs     = median(replay_loaded - replay_clicked)
 */

interface AuditEvent {
  panel: string
  runId: string
  action: 'replay_clicked' | 'replay_loaded' | 'replay_completed'
  timestamp: number
}

const _events: AuditEvent[] = []

/** Maximum in-memory event buffer (audit only — not production telemetry). */
const MAX_EVENTS = 5000

export function logAuditEvent(
  panel: string,
  runId: string,
  action: AuditEvent['action']
): void {
  _events.push({ panel, runId, action, timestamp: Date.now() })
  if (_events.length > MAX_EVENTS) {
    _events.splice(0, _events.length - MAX_EVENTS)
  }
}

/** Clear the in-memory event buffer. Useful for testing and audit resets. */
export function clearAuditEvents(): void {
  _events.length = 0
}

export interface AuditSummary {
  totalClicks: number
  totalLoaded: number
  totalCompleted: number
  completionRate: number
  medianTimeMs: number | null
  byPanel: Record<string, { clicks: number; loaded: number; rate: number }>
}

export function getAuditSummary(): AuditSummary {
  const clicks = _events.filter((e) => e.action === 'replay_clicked')
  const loaded = _events.filter((e) => e.action === 'replay_loaded')
  const completed = _events.filter((e) => e.action === 'replay_completed')

  // Pair clicks with subsequent loads by runId
  const clickToLoadMs: number[] = []
  for (const c of clicks) {
    const load = loaded.find(
      (l) => l.runId === c.runId && l.timestamp >= c.timestamp
    )
    if (load) {
      clickToLoadMs.push(load.timestamp - c.timestamp)
    }
  }

  // Per-panel breakdown
  // Map each runId to the panel of its first click for load attribution
  const runIdToClickPanel: Record<string, string> = {}
  for (const c of clicks) {
    if (!(c.runId in runIdToClickPanel)) {
      runIdToClickPanel[c.runId] = c.panel
    }
  }

  const byPanel: AuditSummary['byPanel'] = {}
  const panels = Array.from(new Set(_events.map((e) => e.panel)))
  for (const p of panels) {
    const pClicks = _events.filter(
      (e) => e.panel === p && e.action === 'replay_clicked'
    ).length
    // Attribute loaded events to the panel of the matching click
    const pLoaded = loaded.filter(
      (l) => runIdToClickPanel[l.runId] === p
    ).length
    byPanel[p] = {
      clicks: pClicks,
      loaded: pLoaded,
      rate: pClicks > 0 ? pLoaded / pClicks : 0,
    }
  }

  const totalClicks = clicks.length
  const totalLoaded = loaded.length

  return {
    totalClicks,
    totalLoaded,
    totalCompleted: completed.length,
    completionRate: totalClicks > 0 ? totalLoaded / totalClicks : 0,
    medianTimeMs: clickToLoadMs.length > 0 ? median(clickToLoadMs) : null,
    byPanel,
  }
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2
}

/** Expose summary on window for console inspection during audit. */
if (typeof window !== 'undefined') {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).uarAudit = {
    summary: getAuditSummary,
    events: () => _events.slice(),
  }
}
