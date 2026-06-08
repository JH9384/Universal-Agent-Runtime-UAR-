import { useState, useCallback, useEffect } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import { TopologyWidget } from './TopologyWidget'
import { TrendPanel } from './TrendPanel'
import { BurnInHistory } from './BurnInHistory'
import { FailureClusterPanel } from './FailureClusterPanel'
import { ConfidenceDriftPanel } from './ConfidenceDriftPanel'
import { TopologyAnalyticsPanel } from './TopologyAnalyticsPanel'
import { FailureHotspotPanel } from './FailureHotspotPanel'
import { RecipeIntelligencePanel } from './RecipeIntelligencePanel'
import { RecommendationPanel } from './RecommendationPanel'
import { TrustTrendPanel } from './TrustTrendPanel'
import { DivergenceDashboard } from './DivergenceDashboard'
import { BurnInTimeline } from './BurnInTimeline'
import { BurnInObservations } from './BurnInObservations'
import SyncStatusPanel from './SyncStatusPanel'
import PluginManager from './PluginManager'
import CredentialVaultPanel from './CredentialVaultPanel'
import MaintenanceWindowPanel from './MaintenanceWindowPanel'
import ActivityLogPanel from './ActivityLogPanel'
import FileTypeSettings from './FileTypeSettings'
import DataSourceRegistryPanel from './DataSourceRegistryPanel'
import SelfUpdatePanel from './SelfUpdatePanel'
import styles from './MissionControlWidget.module.css'

interface ComponentHealth {
  score: number
  status: string
  notes: string[]
}

interface RuntimeHealthData {
  score: number
  tier: string
  components: Record<string, ComponentHealth>
  warnings: string[]
  timestamp: number
}

interface ReplayConfidenceData {
  score?: number
  tier?: string
  warnings?: string[]
}

interface CertificationData {
  score: number
  level: string
  evidence: Record<string, unknown>
  violations: string[]
  timestamp: number
}

interface EntityRetentionData {
  metadata_backend?: {
    list_meta_keys?: boolean
    delete_metadata?: boolean
  }
  entities?: Record<string, {
    namespace?: string
    count?: number | null
    discovery?: string
    retention_capable?: boolean
    sort_field?: string
    error?: string
  }>
  error?: string
}

interface TrustSummaryData {
  system_calibration_error: number | null
  recommendation_type_count: number
  top_trusted: string | null
  top_trust_score: number | null
  drift_count: number
  highly_trusted_count: number
}

interface FleetSignalData {
  id: string
  level: string
  scope: string
  title: string
  message: string
  affected_run_ids: string[]
  latest_run_id: string | null
  linked_incident_ids: string[]
  linked_recommendation_ids: string[]
  trust_delta: number | null
  replay_confidence: number | null
  evidence_refs: string[]
  count: number
  failure_rate: number
  updated_at: number
}

interface FleetSummaryData {
  status: string
  active_signals: number
  critical_signals: number
  warning_signals: number
  top_signal: FleetSignalData | null
  signals: FleetSignalData[]
}

interface MissionControlSnapshot {
  replay_confidence: ReplayConfidenceData | null
  runtime_health: RuntimeHealthData | null
  certification: CertificationData | null
  active_runs: number
  recent_warnings: string[]
  timestamp: number
  trust_summary: TrustSummaryData | null
  entity_retention?: EntityRetentionData | null
  fleet_summary: FleetSummaryData | null
  server_version: string
  uptime_seconds: number
  skills_available: number
  skills_total: number
  circuit_breakers: { name: string; state: string; failures?: number; threshold?: number }[]
}

function tierColor(tier: string): string {
  const t = tier.toLowerCase()
  if (t.includes('gold') || t.includes('verified') || t.includes('nominal')) return styles.tierGreen
  if (t.includes('silver') || t.includes('high') || t.includes('healthy')) return styles.tierBlue
  if (t.includes('medium') || t.includes('degraded') || t.includes('warning')) return styles.tierYellow
  if (t.includes('low') || t.includes('unstable')) return styles.tierOrange
  if (t.includes('experimental') || t.includes('failed') || t.includes('critical')) return styles.tierRed
  return styles.tierGray
}

function ScoreRing({ score, label, tier }: { score: number; label: string; tier: string }) {
  const colorClass = tierColor(tier)
  return (
    <div className={styles.scoreRingCard}>
      <div className={`${styles.scoreRing} ${colorClass}`}>
        <span className={styles.scoreValue}>{score}</span>
          <div className={styles.card}>
            <div className={styles.cardHeader}>Entity Retention</div>
            {entityRetention ? (
              <>
                <div className={styles.bigNumber}>
                  {entityRetention.entities?.snapshots?.retention_capable ? "Ready" : "Watch"}
                </div>
                <div className={styles.subText}>
                  Snapshots: {entityRetention.entities?.snapshots?.count ?? "—"}
                </div>
                <div className={styles.subText}>
                  Keys: {entityRetention.metadata_backend?.list_meta_keys ? "yes" : "no"} · Delete: {entityRetention.metadata_backend?.delete_metadata ? "yes" : "no"}
                </div>
              </>
            ) : (
              <div className={styles.subText}>No entity retention signal yet.</div>
            )}
          </div>

      </div>
      <div className={styles.scoreLabel}>{label}</div>
      <div className={`${styles.scoreTier} ${colorClass}`}>{tier}</div>
    </div>
  )
}

function MiniCard({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`${styles.miniCard} ${className}`}>
      <h4 className={styles.miniCardTitle}>{title}</h4>
      {children}
    </div>
  )
}

interface MissionControlWidgetProps {
  onOpenReplay?: (runId: string) => void
  initialTab?: string
}

const TAB_KEY = 'uar_mc_active_tab'
const TAB_ORDER = ['health', 'trends', 'failures', 'topology', 'intelligence'] as const
type TabKey = typeof TAB_ORDER[number]

function _getSavedTab(): TabKey {
  try {
    const saved = localStorage.getItem(TAB_KEY) as TabKey | null
    if (saved && TAB_ORDER.includes(saved)) return saved
  } catch {
    /* noop */
  }
  return 'health'
}

function _saveTab(tab: TabKey): void {
  try {
    localStorage.setItem(TAB_KEY, tab)
  } catch {
    /* noop */
  }
}

const TAB_LABEL: Record<TabKey, string> = {
  health: 'Health',
  trends: 'Trends',
  failures: 'Failures',
  topology: 'Topology',
  intelligence: 'Intelligence',
}

export function MissionControlWidget({ onOpenReplay, initialTab }: MissionControlWidgetProps) {
  const { data: mc, loading: mcLoading, error: mcError } = useApiFetch<MissionControlSnapshot>(
    '/api/uar/mission-control',
    { interval: 30_000 }
  )

  const [activeTab, setActiveTab] = useState<TabKey>(_getSavedTab)

  useEffect(() => {
    if (initialTab && TAB_ORDER.includes(initialTab as TabKey)) {
      setActiveTab(initialTab as TabKey)
    }
  }, [initialTab])

  const handleTab = useCallback((tab: TabKey) => {
    setActiveTab(tab)
    _saveTab(tab)
  }, [])

  const loading = mcLoading && !mc
  const error = mcError

  if (loading) return <div className={styles.loading}>Loading Mission Control…</div>
  if (error) return <div className={styles.error}>Mission Control failed: {error}</div>
  if (!mc) return null

  const rh = mc.runtime_health
  const rc = mc.replay_confidence
  const cert = mc.certification
  const entityRetention = mc.entity_retention
  const fleet = mc.fleet_summary
  const topFleetSignal = fleet?.top_signal ?? null

  const availableCount = mc.skills_available
  const totalSkills = mc.skills_total
  const openBreakers = mc.circuit_breakers.filter((b) => b.state === 'open')

  return (
    <div className={styles.missionControl}>
      <h3 className={styles.title}>Mission Control</h3>

      {/* Tab bar */}
      <div className={styles.tabBar} role="tablist">
        {TAB_ORDER.map((tab) => (
          <button
            key={tab}
            className={`${styles.tabBtn} ${activeTab === tab ? styles.tabActive : ''}`}
            onClick={() => handleTab(tab)}
            role="tab"
            aria-selected={activeTab === tab}
          >
            {TAB_LABEL[tab]}
          </button>
        ))}
      </div>

      {/* Health tab */}
      {activeTab === 'health' && (
        <div className={styles.tabPanel} role="tabpanel">
          <div className={styles.scoreRingRow}>
            {rh && <ScoreRing score={rh.score} label="Runtime Health" tier={rh.tier} />}
            {rc && typeof rc.score === 'number' && (
              <ScoreRing score={rc.score} label="Replay Confidence" tier={rc.tier || 'Unknown'} />
            )}
            {cert && <ScoreRing score={cert.score} label="Certification" tier={cert.level} />}
          </div>

          <div className={styles.miniCardGrid}>
            <MiniCard title="Active Runs">
              <div className={styles.bigNumber}>{mc.active_runs}</div>
              <div className={styles.bigNumberLabel}>running / pending / queued</div>
            </MiniCard>

            <MiniCard title="Fleet Health">
              {fleet ? (
                <>
                  <div className={styles.skillHealthRow}>
                    <span className={`${styles.skillHealthOk} ${tierColor(fleet.status)}`}>
                      {fleet.active_signals}
                    </span>
                    <span className={styles.skillHealthLabel}>active signal(s)</span>
                  </div>
                  <div className={styles.trustMeta}>
                    <span>Status: {fleet.status}</span>
                    {' · '}
                    <span>{fleet.critical_signals} critical</span>
                    {' · '}
                    <span>{fleet.warning_signals} warning</span>
                  </div>
                  {topFleetSignal ? (
                    <div className={styles.trustMeta}>
                      <strong>{topFleetSignal.title}</strong>
                      <div>{topFleetSignal.message}</div>
                      {topFleetSignal.latest_run_id && onOpenReplay && (
                        <button
                          className={styles.inlineButton}
                          onClick={() => onOpenReplay(topFleetSignal.latest_run_id!)}
                          title={`Open replay ${topFleetSignal.latest_run_id}`}
                        >
                          ▶ Replay {topFleetSignal.latest_run_id.slice(0, 12)}…
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className={styles.okBadge}>Fleet nominal</div>
                  )}
                </>
              ) : (
                <div className={styles.muted}>No fleet summary</div>
              )}
            </MiniCard>

            <MiniCard title="System Health">
              <div className={styles.skillHealthRow}>
                <span className={styles.skillHealthOk}>{availableCount}</span>
                <span className={styles.skillHealthSep}>/</span>
                <span className={styles.skillHealthTotal}>{totalSkills}</span>
                <span className={styles.skillHealthLabel}>skills available</span>
              </div>
              {openBreakers.length > 0 ? (
                <div className={styles.alertBadge} role="status">{openBreakers.length} open circuit breaker(s)</div>
              ) : (
                <div className={styles.okBadge}>All circuit breakers closed</div>
              )}
            </MiniCard>

            <MiniCard title="Burn-In">
              {cert?.evidence && typeof cert.evidence.burnin_score === 'number' ? (
                <>
                  <div className={styles.burninScore}>{cert.evidence.burnin_score as number}%</div>
                  <div className={styles.burninStatus}>
                    {(cert.evidence.burnin_passed as boolean) ? (
                      <span className={styles.okBadge}>Passed</span>
                    ) : (
                      <span className={styles.alertBadge} role="status">Not passed</span>
                    )}
                  </div>
                </>
              ) : (
                <div className={styles.muted}>No burn-in report yet</div>
              )}
            </MiniCard>

            <MiniCard title={`Warnings (${mc.recent_warnings.length})`}>
              {mc.recent_warnings.length === 0 ? (
                <div className={styles.okBadge}>No warnings</div>
              ) : (
                <ul className={styles.warningList}>
                  {mc.recent_warnings.slice(0, 5).map((w, i) => (
                    <li key={`${w}-${i}`} className={styles.warningItem}>{w}</li>
                  ))}
                </ul>
              )}
            </MiniCard>

            <MiniCard title="Trust">
              {mc.trust_summary ? (
                <>
                  <div className={styles.trustScore}>
                    {mc.trust_summary.top_trust_score !== null
                      ? mc.trust_summary.top_trust_score.toFixed(2)
                      : '—'}
                  </div>
                  <div className={styles.trustLabel}>
                    Top: {mc.trust_summary.top_trusted ?? '—'}
                  </div>
                  <div className={styles.trustMeta}>
                    <span>{mc.trust_summary.recommendation_type_count} types</span>
                    {' · '}
                    <span>{mc.trust_summary.highly_trusted_count} highly trusted</span>
                  </div>
                  {mc.trust_summary.drift_count > 0 && (
                    <div className={styles.alertBadge} role="status">
                      {mc.trust_summary.drift_count} drift signal(s)
                    </div>
                  )}
                  {mc.trust_summary.system_calibration_error !== null && (
                    <div className={styles.trustMeta}>
                      Calibration error: {mc.trust_summary.system_calibration_error.toFixed(2)}
                    </div>
                  )}
                </>
              ) : (
                <div className={styles.muted}>No trust data</div>
              )}
            </MiniCard>
          </div>

          {rh && rh.components && Object.keys(rh.components).length > 0 && (
            <div className={styles.componentSection}>
              <h4 className={styles.sectionTitle}>Component Health</h4>
              <div className={styles.componentGrid}>
                {Object.entries(rh.components).map(([name, comp]) => (
                  <div key={name} className={styles.componentItem}>
                    <span className={styles.componentName}>{name}</span>
                    <span className={`${styles.componentScore} ${tierColor(comp.status)}`}>
                      {comp.score}
                    </span>
                    <span className={styles.componentStatus}>{comp.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className={styles.sectionWrap}>
            <SyncStatusPanel />
            <PluginManager />
            <CredentialVaultPanel />
            <MaintenanceWindowPanel />
            <ActivityLogPanel />
            <FileTypeSettings />
            <DataSourceRegistryPanel />
            <SelfUpdatePanel />
          </div>
        </div>
      )}

      {/* Trends tab */}
      {activeTab === 'trends' && (
        <div className={styles.tabPanel} role="tabpanel">
          <BurnInObservations />
          <BurnInTimeline />
          <DivergenceDashboard onOpenReplay={onOpenReplay} />
          <TrustTrendPanel />
          <ConfidenceDriftPanel />
          <TrendPanel />
          <BurnInHistory />
        </div>
      )}

      {/* Failures tab */}
      {activeTab === 'failures' && (
        <div className={styles.tabPanel} role="tabpanel">
          <FailureClusterPanel onOpenReplay={onOpenReplay} />
          <FailureHotspotPanel onOpenReplay={onOpenReplay} />
        </div>
      )}

      {/* Topology tab */}
      {activeTab === 'topology' && (
        <div className={styles.tabPanel} role="tabpanel">
          <div className={styles.topologySection}>
            <TopologyWidget />
          </div>
          <TopologyAnalyticsPanel />
        </div>
      )}

      {/* Intelligence tab */}
      {activeTab === 'intelligence' && (
        <div className={styles.tabPanel} role="tabpanel">
          <RecipeIntelligencePanel onOpenReplay={onOpenReplay} />
          <RecommendationPanel onOpenReplay={onOpenReplay} />
        </div>
      )}

      {/* Footer */}
      <div className={styles.footer}>
        <span className={styles.footerVersion}>{mc.server_version || 'UAR'}</span>
        <span className={styles.footerUptime}>
          Uptime: {mc.uptime_seconds ? formatUptime(mc.uptime_seconds) : '—'}
        </span>
      </div>
    </div>
  )
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
