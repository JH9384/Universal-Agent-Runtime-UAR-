import { useMemo, useState } from 'react'
import styles from './RecipeTimeline.module.css'

type TimelineItem = {
  id: string
  instanceId: string
  label: string
  status: 'running' | 'complete' | 'failed' | 'aborted'
  skills: { name: string; status: 'pending' | 'running' | 'complete' | 'failed' }[]
  isOpen: boolean
  depth: number
  retries: number
  startTime?: number
  endTime?: number
}

type FlatEvent = {
  type: 'recipe' | 'skill'
  label: string
  status: string
  depth: number
  instanceId?: string
  skillName?: string
  durationMs?: number
}

export default function RecipeTimeline({
  events,
  recipes,
}: {
  events: any[]
  recipes: { id: string; label: string }[]
}) {
  const [openRecipes, setOpenRecipes] = useState<Set<string>>(new Set())

  const timeline = useMemo(() => {
    const stack: TimelineItem[] = []
    const result: TimelineItem[] = []
    const recipeSkillMap = new Map<string, Set<string>>()

    for (const e of events) {
      if (e?.type === 'recipe_start') {
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
        recipeSkillMap.set(instanceId, new Set())
      } else if (e?.type === 'recipe_end') {
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
      } else if (e?.type === 'skill_start' && e.skill) {
        const activeRecipe = stack[stack.length - 1]
        if (activeRecipe) {
          activeRecipe.skills.push({ name: e.skill, status: 'running' })
          recipeSkillMap.get(activeRecipe.instanceId)?.add(e.skill)
        }
      } else if (e?.type === 'skill_complete' && e.skill) {
        for (let i = stack.length - 1; i >= 0; i--) {
          const skill = stack[i].skills.find(
            (s) => s.name === e.skill && s.status === 'running'
          )
          if (skill) {
            skill.status = 'complete'
            break
          }
        }
      } else if (e?.type === 'skill_failed' && e.skill) {
        for (let i = stack.length - 1; i >= 0; i--) {
          const skill = stack[i].skills.find((s) => s.name === e.skill)
          if (skill) {
            skill.status = 'failed'
            stack[i].status = 'failed'
            break
          }
        }
      } else if (e?.type === 'recipe_retry') {
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
      }
    }

    while (stack.length > 0) {
      const item = stack.pop()!
      result.push(item)
    }

    return result
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

  const depthIndent = (depth: number) => ({ paddingLeft: `${depth * 16 + 8}px` })

  const durationText = (item: TimelineItem) => {
    if (!item.startTime || !item.endTime) return ''
    const ms = item.endTime - item.startTime
    if (ms < 1000) return `${ms.toFixed(0)}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  return (
    <div className={styles.timeline}>
      {timeline.map((item) => (
        <div
          key={item.instanceId}
          className={styles.recipeBlock}
          style={depthIndent(item.depth)}
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
            <span className={styles.duration}>{durationText(item)}</span>
            <span className={styles.expandIcon}>
              {openRecipes.has(item.instanceId) ? '▼' : '▶'}
            </span>
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
                  style={depthIndent(item.depth + 1)}
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
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      {timeline.length === 0 && (
        <div className={styles.noEvents}>No recipe events found</div>
      )}
    </div>
  )
}
