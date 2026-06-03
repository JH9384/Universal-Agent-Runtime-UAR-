import { useApiFetch } from '../hooks/useApiFetch'
import CollapsibleSection from './CollapsibleSection'
import { AlertBanner } from './AlertBanner'
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

interface TrustSummaryData {
  system_calibration_error: number | null
  recommendation_type_count: number
  top_trusted: string | null
  top_trust_score: number | null
  drift_count: number
  highly_trusted_count: number
}

interface MissionControlSnapshot {
  replay_confidence: ReplayConfidenceData | null
  runtime_health: RuntimeHealthData | null
  certification: CertificationData | null
  active_runs: number
  recent_warnings: string[]
  timestamp: number
  trust_summary: TrustSummaryData | null
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
  if (t.includes('medium') || t.includes('degraded')) return styles.tierYellow
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
}

export function MissionControlWidget({ onOpenReplay }: MissionControlWidgetProps) {
  const { data: mc, loading: mcLoading, error: mcError } = useApiFetch<MissionControlSnapshot>(
    '/api/uar/mission-control',
    { interval: 30_000 }
  )

  const loading = mcLoading && !mc
  const error = mcError

  if (loading) return <div className={styles.loading}>Loading Mission Control…</div>
  if (error) return <div className={styles.error}>Mission Control failed: {error}</div>
  if (!mc) return null

  const rh = mc.runtime_health
  const rc = mc.replay_confidence
  const cert = mc.certification

  const availableCount = mc.skills_available
  const totalSkills = mc.skills_total
  const openBreakers = mc.circuit_breakers.filter((b) => b.state === 'open')

  return (
    <div className={styles.missionControl}>
      <h3 className={styles.title}>Mission Control</h3>

      {/* Overview — always visible */}
      <div className={styles.sectionWrap}>
        <CollapsibleSection id="mc-overview" title="Overview" defaultOpen={true}>
        {/* Alert banner — operator interruption */}
        <AlertBanner />

        {/* Score rings — primary signals */}
        <div className={styles.scoreRingRow}>
          {rh && <ScoreRing score={rh.score} label="Runtime Health" tier={rh.tier} />}
          {rc && typeof rc.score === 'number' && (
            <ScoreRing score={rc.score} label="Replay Confidence" tier={rc.tier || 'Unknown'} />
          )}
          {cert && <ScoreRing score={cert.score} label="Certification" tier={cert.level} />}
        </div>

        {/* Secondary cards */}
        <div className={styles.miniCardGrid}>
          <MiniCard title="Active Runs">
            <div className={styles.bigNumber}>{mc.active_runs}</div>
            <div className={styles.bigNumberLabel}>running / pending / queued</div>
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

        {/* Component breakdown */}
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
        </CollapsibleSection>
      </div>

      {/* Recommendations — operator actions */}
      <div className={styles.sectionWrap}>
        <CollapsibleSection id="mc-recommendations" title="Recommendations" defaultOpen={true}>
        <RecommendationPanel onOpenReplay={onOpenReplay} />
        </CollapsibleSection>
      </div>

      {/* Evidence — drill down */}
      <div className={styles.sectionWrap}>
        <CollapsibleSection id="mc-evidence" title="Evidence" defaultOpen={false}>
        <BurnInObservations />
        <BurnInTimeline />
        <DivergenceDashboard onOpenReplay={onOpenReplay} />
        <TrustTrendPanel />
        <ConfidenceDriftPanel />
        <TrendPanel />
        <BurnInHistory />
        </CollapsibleSection>
      </div>

      {/* Failures — drill down */}
      <div className={styles.sectionWrap}>
        <CollapsibleSection id="mc-failures" title="Failures" defaultOpen={false}>
        <FailureClusterPanel onOpenReplay={onOpenReplay} />
        <FailureHotspotPanel onOpenReplay={onOpenReplay} />
        </CollapsibleSection>
      </div>

      {/* Topology — drill down */}
      <div className={styles.sectionWrap}>
        <CollapsibleSection id="mc-topology" title="Topology" defaultOpen={false}>
        <div className={styles.topologySection}>
          <TopologyWidget />
        </div>
        <TopologyAnalyticsPanel />
        <RecipeIntelligencePanel onOpenReplay={onOpenReplay} />
        </CollapsibleSection>
      </div>

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
