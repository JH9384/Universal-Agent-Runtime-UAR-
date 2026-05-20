import { useMemo, useState } from 'react'
import styles from './RecipeTimeline.module.css'

type TimelineItem = {
  id: string
  instanceId: string
  label: string
  status: 'running' | 'complete' | 'failed' | 'aborted'
  skills: { name: string; status: 'pending' | 'running' | 'complete' | 'failed' }[]
  isOpen: boolean
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
        const item: TimelineItem = {
          id: recipeId,
          instanceId,
          label,
          status: 'running',
          skills: [],
          isOpen: true,
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
      }
    }

    while (stack.length > 0) {
      const item = stack.pop()!
      item.status = 'aborted'
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

  if (timeline.length === 0) {
    return (
      <div className={styles.timelineContainer}>
        <div className={styles.timelineEmpty}>
          No recipe events yet. Start a run to see the timeline.
        </div>
      </div>
    )
  }

  const statusClass = (status: string) => {
    switch (status) {
      case 'running':
        return styles.statusRunning
      case 'complete':
        return styles.statusComplete
      case 'failed':
        return styles.statusFailed
      case 'aborted':
        return styles.statusAborted
      default:
        return ''
    }
  }

  const skillClass = (status: string) => {
    switch (status) {
      case 'complete':
        return styles.timelineSkillComplete
      case 'failed':
        return styles.timelineSkillFailed
      case 'running':
        return styles.timelineSkillRunning
      default:
        return ''
    }
  }

  return (
    <div className={styles.timelineContainer}>
      {timeline.map((recipe) => {
        const isOpen = openRecipes.has(recipe.instanceId)
        return (
          <div key={recipe.instanceId} className={styles.timelineRecipe}>
            <div
              className={styles.timelineRecipeHeader}
              onClick={() => toggleRecipe(recipe.instanceId)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ')
                  toggleRecipe(recipe.instanceId)
              }}
            >
              <span className={styles.timelineRecipeIcon}>
                {isOpen ? '▼' : '▶'}
              </span>
              <span className={styles.timelineRecipeLabel}>{recipe.label}</span>
              <span
                className={`${styles.timelineRecipeStatus} ${statusClass(recipe.status)}`}
              >
                {recipe.status}
              </span>
            </div>
            {isOpen && (
              <div className={styles.timelineSkills}>
                {recipe.skills.length === 0 ? (
                  <div className={styles.timelineEmptySkill}>
                    No skills executed yet
                  </div>
                ) : (
                  recipe.skills.map((skill, idx) => (
                    <div
                      key={idx}
                      className={`${styles.timelineSkill} ${skillClass(skill.status)}`}
                    >
                      <span className={styles.timelineSkillName}>
                        {skill.name}
                      </span>
                      <span className={styles.timelineSkillStatus}>
                        {skill.status}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
