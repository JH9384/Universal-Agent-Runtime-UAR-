import { useEffect, useMemo, useState } from 'react'
import styles from './RecipeTimeline.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SkillStatus = 'pending' | 'running' | 'complete' | 'failed'

type TimelineItem = {
  id: string
  instanceId: string
  label: string
  status: 'running' | 'complete' | 'failed' | 'aborted'
  skills: { name: string; status: SkillStatus; startTs?: number; endTs?: number }[]
  isOpen: boolean
  depth: number
  retries: number
  startTime?: number
  endTime?: number
}

type StandaloneSkill = {
  name: string
  status: SkillStatus
  startTs?: number
  endTs?: number
}

type RunMeta = {
  runId: string
  goalId: string
  startTs: number
  endTs?: number
  status: string
  skillCount: number
  errorCount: number
  recipeCount: number
}

type DetailEvent = {
  type: string
  timestamp: number
  skill?: string
  payload?: Record<string, unknown>
  error?: string
}

export default function RecipeTimeline({
  events,
  recipes,
}: {
  events: any[]
  recipes: { id: string; label: string }[]
}) {
  const [openRecipes, setOpenRecipes] = useState<Set<string>>(new Set())
  const [detailEvent, setDetailEvent] = useState<DetailEvent | null>(null)

  useEffect(() => {
    if (!detailEvent) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDetailEvent(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [detailEvent])

  const { meta, timeline, standaloneSkills } = useMemo(() => {
    // ---- meta --------------------------------------------------------------
    const first = events[0]
    const last = events[events.length - 1]
    const runMeta: RunMeta = {
      runId: first?.run_id || '—',
      goalId: first?.goal_id || '—',
      startTs: first?.timestamp || 0,
      endTs: last?.timestamp,
      status: 'unknown',
      skillCount: 0,
      errorCount: 0,
      recipeCount: 0,
    }

    // ---- timeline builder ---------------------------------------------------
    const stack: TimelineItem[] = []
    const result: TimelineItem[] = []
    const standalone: StandaloneSkill[] = []
    const standaloneRunning = new Map<string, { startTs: number }>()

    for (const e of events) {
      const etype = e?.type
      if (etype === 'recipe_start') {
        runMeta.recipeCount++
        const recipeId = e.payload?.recipe_id || ''
        const instanceId = e.payload?.instance_id || ''
        const label = recipes.find((r) => r.id === recipeId)?.label || recipeId
        const depth = stack.length
        const item: TimelineItem = {
          id: recipeId,
          instanceId,
          label,
          status: 'running',
          skills: [],
          isOpen: true,
          depth,
          retries: 0,
          startTime: e.timestamp,
        }
        stack.push(item)
      } else if (etype === 'recipe_end') {
        const instanceId = e.payload?.instance_id || ''
        const aborted = e.payload?.status === 'aborted'
        if (stack.length > 0) {
          const item = stack.pop()!
          if (item.instanceId === instanceId) {
            item.status = aborted
              ? 'aborted'
              : item.status === 'running'
                ? 'complete'
                : item.status
            item.endTime = e.timestamp
          }
          result.push(item)
        }
      } else if (etype === 'skill_start' && e.skill) {
        const activeRecipe = stack[stack.length - 1]
        if (activeRecipe) {
          activeRecipe.skills.push({ name: e.skill, status: 'running', startTs: e.timestamp })
        } else {
          standaloneRunning.set(e.skill, { startTs: e.timestamp })
        }
      } else if (etype === 'skill_complete' && e.skill) {
        let found = false
        for (let i = stack.length - 1; i >= 0; i--) {
          const skill = stack[i].skills.find(
            (s) => s.name === e.skill && s.status === 'running'
          )
          if (skill) {
            skill.status = 'complete'
            skill.endTs = e.timestamp
            found = true
            break
          }
        }
        if (!found) {
          const run = standaloneRunning.get(e.skill)
          standalone.push({
            name: e.skill,
            status: 'complete',
            startTs: run?.startTs,
            endTs: e.timestamp,
          })
          standaloneRunning.delete(e.skill)
        }
      } else if (etype === 'skill_failed' && e.skill) {
        let found = false
        for (let i = stack.length - 1; i >= 0; i--) {
          const skill = stack[i].skills.find((s) => s.name === e.skill)
          if (skill) {
            skill.status = 'failed'
            skill.endTs = e.timestamp
            stack[i].status = 'failed'
            found = true
            break
          }
        }
        if (!found) {
          const run = standaloneRunning.get(e.skill)
          standalone.push({
            name: e.skill,
            status: 'failed',
            startTs: run?.startTs,
            endTs: e.timestamp,
          })
          standaloneRunning.delete(e.skill)
        }
      } else if (etype === 'recipe_retry') {
        const instanceId = e.payload?.instance_id || ''
        for (let i = stack.length - 1; i >= 0; i--) {
          if (stack[i].instanceId === instanceId) {
            stack[i].retries += 1
            break
          }
        }
        for (const item of result) {
          if (item.instanceId === instanceId) {
            item.retries += 1
            break
          }
        }
      } else if (etype === 'error' && e.error) {
        runMeta.errorCount++
      }
    }

    while (stack.length > 0) {
      const item = stack.pop()!
      result.push(item)
    }

    // ---- compute aggregate stats -------------------------------------------
    for (const item of result) {
      runMeta.skillCount += item.skills.length
    }
    runMeta.skillCount += standalone.length

    // Determine overall status from terminal event
    if (last?.payload?.status) {
      runMeta.status = last.payload.status
    } else if (last?.type === 'complete') {
      runMeta.status = 'completed'
    } else if (events.some((e) => e.type === 'error' || e.type === 'skill_failed')) {
      runMeta.status = 'failed'
    } else if (events.some((e) => e.type === 'recipe_end' && e.payload?.status === 'aborted')) {
      runMeta.status = 'aborted'
    } else if (events.length > 0 && !last?.type?.includes('end') && !last?.type?.includes('complete')) {
      runMeta.status = 'running'
    }

    return { meta: runMeta, timeline: result, standaloneSkills: standalone }
  }, [events, recipes])

  const toggleRecipe = (instanceId: string) => {
    setOpenRecipes((prev) => {
      const next = new Set(prev)
      if (next.has(instanceId)) next.delete(instanceId)
      else next.add(instanceId)
      return next
    })
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'complete':
      case 'completed':
        return '✅'
      case 'failed':
        return '❌'
      case 'aborted':
        return '🚫'
      case 'running':
        return '⏳'
      default:
        return '⏳'
    }
  }

  const statusLabelClass = (status: string) => {
    switch (status) {
      case 'complete':
      case 'completed':
        return styles.statusComplete
      case 'failed':
        return styles.statusFailed
      case 'aborted':
        return styles.statusAborted
      case 'running':
        return styles.statusRunning
      default:
        return ''
    }
  }

  const durationText = (start?: number, end?: number) => {
    if (!start || !end) return ''
    const ms = end - start
    if (ms < 1000) return `${ms.toFixed(0)}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const formatTs = (ts: number) => {
    if (!ts) return '—'
    const d = new Date(ts * 1000)
    return d.toLocaleTimeString()
  }

  const showRecipeDetail = (item: TimelineItem) => {
    setDetailEvent({
      type: 'recipe',
      timestamp: item.startTime || 0,
      payload: {
        recipe_id: item.id,
        instance_id: item.instanceId,
        label: item.label,
        status: item.status,
        retries: item.retries,
        skills: item.skills.map((s) => s.name),
        duration_sec: item.endTime && item.startTime
          ? Math.round((item.endTime - item.startTime) * 100) / 100
          : undefined,
      },
    })
  }

  const showSkillDetail = (
    name: string,
    status: SkillStatus,
    startTs?: number,
    endTs?: number
  ) => {
    setDetailEvent({
      type: 'skill',
      timestamp: startTs || 0,
      skill: name,
      payload: {
        status,
        duration_sec: endTs && startTs
          ? Math.round((endTs - startTs) * 100) / 100
          : undefined,
      },
    })
  }

  return (
    <div className={styles.timeline}>
      {/* ---- Run Header ---------------------------------------------------- */}
      <div className={styles.runHeader}>
        <div className={styles.runHeaderRow}>
          <span className={styles.runHeaderId} title={`Run: ${meta.runId}`}>
            🏷️ {meta.runId}
          </span>
          <span className={`${styles.runHeaderStatus} ${statusLabelClass(meta.status)}`}>
            {meta.status}
          </span>
        </div>
        <div className={styles.runHeaderMeta}>
          <span>🎯 {meta.goalId}</span>
          <span>🕒 {formatTs(meta.startTs)}</span>
          {meta.endTs && <span>→ {formatTs(meta.endTs)}</span>}
          <span>({durationText(meta.startTs, meta.endTs) || 'in progress'})</span>
        </div>
      </div>

      {/* ---- Summary Bar --------------------------------------------------- */}
      <div className={styles.summaryBar}>
        <span className={styles.summaryItem}>
          <strong>{meta.skillCount}</strong> skills
        </span>
        <span className={styles.summaryItem}>
          <strong>{meta.recipeCount}</strong> recipes
        </span>
        <span className={styles.summaryItem}>
          <strong>{meta.errorCount}</strong> errors
        </span>
        <span className={styles.summaryItem}>
          <strong>{events.length}</strong> events
        </span>
      </div>

      {/* ---- Recipe Timeline ----------------------------------------------- */}
      {timeline.map((item) => (
        <div
          key={item.instanceId}
          className={styles.recipeBlock}
          data-depth={item.depth}
        >
          <div
            className={styles.recipeHeader}
            onClick={() => toggleRecipe(item.instanceId)}
          >
            <span className={styles.statusIcon}>{statusIcon(item.status)}</span>
            <span className={styles.recipeLabel}>{item.label}</span>
            {item.retries > 0 && (
              <span className={styles.retryBadge} title="Retry count">
                🔄 {item.retries}
              </span>
            )}
            <span className={styles.duration}>{durationText(item.startTime, item.endTime)}</span>
            <span className={styles.expandIcon}>
              {openRecipes.has(item.instanceId) ? '▼' : '▶'}
            </span>
            <button
              className={styles.detailButton}
              onClick={(e) => {
                e.stopPropagation()
                showRecipeDetail(item)
              }}
              title="View details"
              aria-label={`View details for ${item.label}`}
            >
              ℹ️
            </button>
          </div>
          {openRecipes.has(item.instanceId) && (
            <div className={styles.skillsList}>
              {item.skills.length === 0 && (
                <div className={styles.noSkills}>No skills executed</div>
              )}
              {item.skills.map((skill, idx) => (
                <div
                  key={`${skill.name}-${idx}`}
                  className={styles.skillItem}
                  data-depth={item.depth + 1}
                  onClick={() => showSkillDetail(skill.name, skill.status, skill.startTs, skill.endTs)}
                >
                  <span className={styles.statusIcon}>
                    {skill.status === 'complete'
                      ? '✅'
                      : skill.status === 'failed'
                        ? '❌'
                        : skill.status === 'running'
                          ? '⏳'
                          : '⏸️'}
                  </span>
                  <span className={styles.skillName}>{skill.name}</span>
                  <span className={styles.skillDuration}>{durationText(skill.startTs, skill.endTs)}</span>
                  <button
                    className={styles.detailButton}
                    onClick={(e) => {
                      e.stopPropagation()
                      showSkillDetail(skill.name, skill.status, skill.startTs, skill.endTs)
                    }}
                    title="View details"
                    aria-label={`View details for ${skill.name}`}
                  >
                    ℹ️
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* ---- Standalone Skills --------------------------------------------- */}
      {standaloneSkills.length > 0 && (
        <div className={styles.standaloneSection}>
          <div className={styles.standaloneHeader}>⚡ Standalone Skills</div>
          {standaloneSkills.map((skill, idx) => (
            <div
              key={`${skill.name}-${idx}`}
              className={styles.skillItem}
              onClick={() => showSkillDetail(skill.name, skill.status, skill.startTs, skill.endTs)}
            >
              <span className={styles.statusIcon}>
                {skill.status === 'complete'
                  ? '✅'
                  : skill.status === 'failed'
                    ? '❌'
                    : '⏸️'}
              </span>
              <span className={styles.skillName}>{skill.name}</span>
              <span className={styles.skillDuration}>{durationText(skill.startTs, skill.endTs)}</span>
              <button
                className={styles.detailButton}
                onClick={(e) => {
                  e.stopPropagation()
                  showSkillDetail(skill.name, skill.status, skill.startTs, skill.endTs)
                }}
                title="View details"
                aria-label={`View details for ${skill.name}`}
              >
                ℹ️
              </button>
            </div>
          ))}
        </div>
      )}

      {timeline.length === 0 && standaloneSkills.length === 0 && (
        <div className={styles.noEvents}>No events found</div>
      )}

      {/* ---- Details Drawer ------------------------------------------------ */}
      {detailEvent && (
        <div
          className={styles.detailOverlay}
          onClick={() => setDetailEvent(null)}
          role="presentation"
        >
          <div
            className={styles.detailDrawer}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="detail-title"
          >
            <div className={styles.detailHeader}>
              <strong id="detail-title">Event Details</strong>
              <button
                className={styles.detailClose}
                onClick={() => setDetailEvent(null)}
                aria-label="Close details"
              >
                ✕
              </button>
            </div>
            <div className={styles.detailBody}>
              <div className={styles.detailRow}>
                <span className={styles.detailLabel}>Type</span>
                <span className={styles.detailValue}>{detailEvent.type}</span>
              </div>
              <div className={styles.detailRow}>
                <span className={styles.detailLabel}>Timestamp</span>
                <span className={styles.detailValue}>{formatTs(detailEvent.timestamp)}</span>
              </div>
              {detailEvent.skill && (
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Skill</span>
                  <span className={styles.detailValue}>{detailEvent.skill}</span>
                </div>
              )}
              {detailEvent.error && (
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Error</span>
                  <span className={`${styles.detailValue} ${styles.detailError}`}>{detailEvent.error}</span>
                </div>
              )}
              {detailEvent.payload && Object.keys(detailEvent.payload).length > 0 && (
                <div className={styles.detailPayload}>
                  <div className={styles.detailLabel}>Payload</div>
                  <pre className={styles.detailPre}>
                    {JSON.stringify(detailEvent.payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
