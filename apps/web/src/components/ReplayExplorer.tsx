import { useState, useMemo, useEffect, useRef } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import { logAuditEvent } from '../utils/analyticsInstrumentation'
import styles from './ReplayExplorer.module.css'

type EventItem = any

interface ReplayExplorerData {
  run_id: string
  summary: {
    run_id: string
    goal_id: string | null
    status: string | null
    skills: string[]
    created_at: string | null
  }
  timeline: Record<string, unknown>
  confidence: {
    score?: number
    tier?: string
    warnings?: string[]
    [key: string]: unknown
  }
  failure_path: EventItem[]
  events: EventItem[]
}

interface ReplayExplorerProps {
  runId: string
  onClose: () => void
}

const TABS = ['Summary', 'Timeline', 'Confidence', 'Failure Path', 'Events'] as const
type TabName = (typeof TABS)[number]

function statusColor(status: string | null): string {
  const s = (status || '').toLowerCase()
  if (s === 'completed' || s === 'success') return styles.statusGreen
  if (s === 'failed' || s === 'error') return styles.statusRed
  if (s === 'running' || s === 'pending') return styles.statusBlue
  if (s === 'partial') return styles.statusYellow
  return styles.statusGray
}

function confidenceColor(tier: string | undefined): string {
  const t = (tier || '').toLowerCase()
  if (t === 'verified') return styles.tierGreen
  if (t === 'high') return styles.tierBlue
  if (t === 'medium') return styles.tierYellow
  if (t === 'low') return styles.tierOrange
  if (t === 'failed') return styles.tierRed
  return styles.tierGray
}

function EventIcon({ type }: { type: string | undefined }) {
  const t = (type || '').toLowerCase()
  if (t.includes('skill_start')) return <span className={styles.eventIcon}>▶️</span>
  if (t.includes('skill_end')) return <span className={styles.eventIcon}>✅</span>
  if (t.includes('recipe_start')) return <span className={styles.eventIcon}>🍳</span>
  if (t.includes('recipe_end')) return <span className={styles.eventIcon}>🍳✅</span>
  if (t.includes('error')) return <span className={styles.eventIcon}>❌</span>
  if (t.includes('retry')) return <span className={styles.eventIcon}>🔄</span>
  if (t.includes('heartbeat')) return <span className={styles.eventIcon}>💓</span>
  return <span className={styles.eventIcon}>•</span>
}

function JsonTree({ data, depth = 0 }: { data: unknown; depth?: number }) {
  if (data === null) return <span className={styles.jsonNull}>null</span>
  if (typeof data === 'undefined') return <span className={styles.jsonNull}>undefined</span>
  if (typeof data === 'string') return <span className={styles.jsonString}>{JSON.stringify(data)}</span>
  if (typeof data === 'number') return <span className={styles.jsonNumber}>{data}</span>
  if (typeof data === 'boolean') return <span className={styles.jsonBoolean}>{String(data)}</span>
  if (Array.isArray(data)) {
    if (data.length === 0) return <span>[]</span>
    return (
      <span>
        [<span className={styles.jsonToggle} />]
        <div className={styles.jsonChildren}>
          {data.map((item, i) => (
            <div key={i} className={styles.jsonLine}>
              <JsonTree data={item} depth={depth + 1} />
              {i < data.length - 1 && ','}
            </div>
          ))}
        </div>
      </span>
    )
  }
  if (typeof data === 'object') {
    const entries = Object.entries(data)
    if (entries.length === 0) return <span>{}</span>
    return (
      <span>
        {'{'}<span className={styles.jsonToggle} />
        <div className={styles.jsonChildren}>
          {entries.map(([key, value], i) => (
            <div key={key} className={styles.jsonLine}>
              <span className={styles.jsonKey}>{JSON.stringify(key)}</span>:{' '}
              <JsonTree data={value} depth={depth + 1} />
              {i < entries.length - 1 && ','}
            </div>
          ))}
        </div>
        {'}'}
      </span>
    )
  }
  return <span>{String(data)}</span>
}

export function ReplayExplorer({ runId, onClose }: ReplayExplorerProps) {
  const [activeTab, setActiveTab] = useState<TabName>('Summary')

  const { data, loading, error } = useApiFetch<ReplayExplorerData>(
    `/api/uar/runs/${encodeURIComponent(runId)}/explorer`
  )

  const summary = data?.summary
  const confidence = data?.confidence || {}
  const events = useMemo(() => data?.events || [], [data])
  const failurePath = useMemo(() => data?.failure_path || [], [data])

  const mountTime = useRef<number>(Date.now())
  useEffect(() => {
    logAuditEvent('replay_explorer', runId, 'replay_loaded')
    mountTime.current = Date.now()
    return () => {
      const viewedMs = Date.now() - mountTime.current
      if (viewedMs >= 3000) {
        logAuditEvent('replay_explorer', runId, 'replay_completed')
      }
    }
  }, [runId])

  if (loading) {
    return (
      <div className={styles.explorerOverlay} onClick={onClose} role="presentation">
        <div className={styles.explorerPanel} onClick={(e) => e.stopPropagation()}>
          <div className={styles.explorerHeader}>
            <strong>🔍 Replay Explorer</strong>
            <button className={styles.closeButton} onClick={onClose} aria-label="Close explorer">✕</button>
          </div>
          <div className={styles.explorerBody}>Loading run {runId}…</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.explorerOverlay} onClick={onClose} role="presentation">
        <div className={styles.explorerPanel} onClick={(e) => e.stopPropagation()}>
          <div className={styles.explorerHeader}>
            <strong>🔍 Replay Explorer</strong>
            <button className={styles.closeButton} onClick={onClose} aria-label="Close explorer">✕</button>
          </div>
          <div className={styles.explorerBody}>Error: {error}</div>
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className={styles.explorerOverlay} onClick={onClose} role="presentation">
      <div className={styles.explorerPanel} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.explorerHeader}>
          <div>
            <strong>🔍 Replay Explorer</strong>
            {summary && (
              <div className={styles.runMeta}>
                <span className={styles.runId}>{runId}</span>
                {summary.status && (
                  <span className={`${styles.statusPill} ${statusColor(summary.status)}`}>
                    {summary.status}
                  </span>
                )}
              </div>
            )}
          </div>
          <button className={styles.closeButton} onClick={onClose} aria-label="Close explorer">✕</button>
        </div>

        {/* Tabs */}
        <div className={styles.tabNav}>
          {TABS.map((tab) => (
            <button
              key={tab}
              className={`${styles.tabButton} ${activeTab === tab ? styles.tabActive : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className={styles.explorerBody}>
          {/* Summary Tab */}
          {activeTab === 'Summary' && (
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <h4 className={styles.cardTitle}>Run</h4>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>Run ID</span>
                  <span className={styles.summaryValue}>{runId}</span>
                </div>
                {summary?.goal_id && (
                  <div className={styles.summaryRow}>
                    <span className={styles.summaryLabel}>Goal</span>
                    <span className={styles.summaryValue}>{summary.goal_id}</span>
                  </div>
                )}
                {summary?.created_at && (
                  <div className={styles.summaryRow}>
                    <span className={styles.summaryLabel}>Created</span>
                    <span className={styles.summaryValue}>{summary.created_at}</span>
                  </div>
                )}
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>Status</span>
                  <span className={`${styles.statusPillInline} ${statusColor(summary?.status || null)}`}>
                    {summary?.status || 'unknown'}
                  </span>
                </div>
              </div>

              <div className={styles.summaryCard}>
                <h4 className={styles.cardTitle}>Skills</h4>
                <div className={styles.skillChips}>
                  {summary?.skills?.map((skill) => (
                    <span key={skill} className={styles.skillChip}>{skill}</span>
                  )) || <span className={styles.muted}>No skills</span>}
                </div>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>Events</span>
                  <span className={styles.summaryValue}>{events.length}</span>
                </div>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>Failures</span>
                  <span className={styles.summaryValue}>{failurePath.length}</span>
                </div>
              </div>

              <div className={styles.summaryCard}>
                <h4 className={styles.cardTitle}>Replay Confidence</h4>
                {typeof confidence.score === 'number' ? (
                  <>
                    <div className={styles.confidenceScoreDisplay}>
                      <span className={styles.confidenceBigNumber}>{confidence.score}</span>
                      <span className={`${styles.confidenceTierBadge} ${confidenceColor(confidence.tier)}`}>
                        {confidence.tier || 'Unknown'}
                      </span>
                    </div>
                    {(confidence.warnings?.length || 0) > 0 && (
                      <div className={styles.warningBox}>
                        <strong>{confidence.warnings!.length} warning(s)</strong>
                        <ul className={styles.warningList}>
                          {confidence.warnings!.map((w, i) => (
                            <li key={i}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                ) : (
                  <span className={styles.muted}>No confidence data</span>
                )}
              </div>
            </div>
          )}

          {/* Timeline Tab */}
          {activeTab === 'Timeline' && (
            <div className={styles.timeline}>
              {events.length === 0 ? (
                <div className={styles.emptyState}>No events recorded for this run.</div>
              ) : (
                events.map((ev, i) => {
                  const type = String(ev.type || '')
                  const hasError = ev.error || type === 'error'
                  return (
                    <div
                      key={i}
                      className={`${styles.timelineItem} ${hasError ? styles.timelineItemError : ''}`}
                    >
                      <div className={styles.timelineIcon}>
                        <EventIcon type={type} />
                      </div>
                      <div className={styles.timelineContent}>
                        <div className={styles.timelineHeader}>
                          <span className={styles.timelineType}>{type}</span>
                          {ev.skill && <span className={styles.timelineSkill}>{String(ev.skill)}</span>}
                          {ev.timestamp && (
                            <span className={styles.timelineTime}>
                              {new Date(Number(ev.timestamp)).toLocaleTimeString()}
                            </span>
                          )}
                        </div>
                        {ev.error && (
                          <div className={styles.timelineError}>{String(ev.error)}</div>
                        )}
                        {ev.payload && (
                          <details className={styles.timelinePayload}>
                            <summary>Payload</summary>
                            <pre className={styles.codeBlock}>
                              {JSON.stringify(ev.payload, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          )}

          {/* Confidence Tab */}
          {activeTab === 'Confidence' && (
            <div className={styles.confidencePanel}>
              {typeof confidence.score === 'number' ? (
                <>
                  <div className={styles.confidenceHeader}>
                    <div className={styles.confidenceRing}>
                      <span className={styles.confidenceRingValue}>{confidence.score}</span>
                    </div>
                    <div>
                      <h3 className={styles.confidenceTitle}>
                        Tier:{' '}
                        <span className={`${styles.confidenceTierLarge} ${confidenceColor(confidence.tier)}`}>
                          {confidence.tier || 'Unknown'}
                        </span>
                      </h3>
                      <p className={styles.confidenceSubtitle}>
                        Based on event completeness, schema validity, and timeline integrity.
                      </p>
                    </div>
                  </div>

                  {(confidence.warnings?.length || 0) > 0 && (
                    <div className={styles.warningSection}>
                      <h4 className={styles.cardTitle}>Warnings</h4>
                      {confidence.warnings!.map((w, i) => (
                        <div key={i} className={styles.warningCard}>{w}</div>
                      ))}
                    </div>
                  )}

                  <div className={styles.evidenceSection}>
                    <h4 className={styles.cardTitle}>Evidence</h4>
                    <div className={styles.codeBlock}>
                      <JsonTree data={confidence} />
                    </div>
                  </div>
                </>
              ) : (
                <div className={styles.emptyState}>No confidence data available for this run.</div>
              )}
            </div>
          )}

          {/* Failure Path Tab */}
          {activeTab === 'Failure Path' && (
            <div>
              {failurePath.length === 0 ? (
                <div className={styles.emptyState}>No failures detected in this run.</div>
              ) : (
                <div className={styles.failureList}>
                  {failurePath.map((ev, i) => (
                    <div key={i} className={styles.failureCard}>
                      <div className={styles.failureHeader}>
                        <EventIcon type={String(ev.type)} />
                        <span className={styles.failureType}>{String(ev.type)}</span>
                        {ev.skill && <span className={styles.failureSkill}>{String(ev.skill)}</span>}
                        {ev.timestamp && (
                          <span className={styles.failureTime}>
                            {new Date(Number(ev.timestamp)).toLocaleTimeString()}
                          </span>
                        )}
                      </div>
                      {ev.error && (
                        <div className={styles.failureError}>{String(ev.error)}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Events Tab (Raw) */}
          {activeTab === 'Events' && (
            <div className={styles.rawPanel}>
              <h4 className={styles.cardTitle}>Raw Events ({events.length})</h4>
              <div className={styles.codeBlock}>
                <JsonTree data={events} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
