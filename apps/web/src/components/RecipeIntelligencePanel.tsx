import { useMemo } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './RecipeIntelligencePanel.module.css'

interface RecipeData {
  recipe: string
  executions: number
  success_rate: number
  failure_rate: number
  avg_confidence: number | null
  avg_duration_ms: number | null
  last_execution: number
  classification: string
}

interface IntelligenceResponse {
  hours: number
  total_runs: number
  recipes: RecipeData[]
}

function classBadge(cls: string): string {
  const c = cls.toLowerCase()
  if (c === 'recommended') return styles.badgeRecommended
  if (c === 'retire') return styles.badgeRetire
  return styles.badgeMonitor
}

function classLabel(cls: string): string {
  const c = cls.toLowerCase()
  if (c === 'recommended') return '⭐ Recommended'
  if (c === 'retire') return '🗑️ Retire'
  return '👁️ Monitor'
}

function Duration({ ms }: { ms: number | null }) {
  if (ms === null) return <span>—</span>
  if (ms < 1000) return <span>{ms}ms</span>
  return <span>{(ms / 1000).toFixed(1)}s</span>
}

function RecipeTable({ recipes }: { recipes: RecipeData[] }) {
  if (recipes.length === 0) return <div className={styles.emptyBlock}>None</div>
  return (
    <div className={styles.recipeList}>
      {recipes.map((r) => (
        <div key={r.recipe} className={styles.recipeCard}>
          <div className={styles.recipeHeader}>
            <span className={styles.recipeName}>{r.recipe}</span>
            <span className={`${styles.classBadge} ${classBadge(r.classification)}`}>
              {classLabel(r.classification)}
            </span>
          </div>
          <div className={styles.recipeStats}>
            <span>{Math.round(r.success_rate * 100)}% success</span>
            <span>{r.executions} runs</span>
            {r.avg_confidence !== null && (
              <span>conf {Math.round(r.avg_confidence)}</span>
            )}
            {r.avg_duration_ms !== null && (
              <span><Duration ms={r.avg_duration_ms} /></span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export function RecipeIntelligencePanel() {
  const { data, loading, error } = useApiFetch<IntelligenceResponse>(
    '/api/uar/recipes/intelligence?hours=168'
  )

  const recommended = useMemo(
    () => (data?.recipes || []).filter((r) => r.classification === 'recommended'),
    [data]
  )
  const monitor = useMemo(
    () => (data?.recipes || []).filter((r) => r.classification === 'monitor'),
    [data]
  )
  const retire = useMemo(
    () => (data?.recipes || []).filter((r) => r.classification === 'retire'),
    [data]
  )

  if (loading) return <div className={styles.loading}>Loading recipe intelligence…</div>
  if (error) return <div className={styles.error}>Recipe intelligence failed: {error}</div>

  return (
    <div className={styles.intelPanel}>
      <h4 className={styles.panelTitle}>Recipe Intelligence</h4>
      <p className={styles.panelDesc}>
        {data?.recipes?.length ?? 0} recipes observed across {data?.total_runs ?? 0} runs
        (last {data?.hours ?? 168}h)
      </p>

      {/* Recommended */}
      <div className={styles.section}>
        <h5 className={styles.sectionTitle}>⭐ Recommended</h5>
        <RecipeTable recipes={recommended} />
      </div>

      {/* Monitor */}
      <div className={styles.section}>
        <h5 className={styles.sectionTitle}>👁️ Monitor</h5>
        <RecipeTable recipes={monitor} />
      </div>

      {/* Retire Candidates */}
      <div className={styles.section}>
        <h5 className={styles.sectionTitle}>🗑️ Retire Candidates</h5>
        <RecipeTable recipes={retire} />
      </div>

      {(!data || data.recipes.length === 0) && (
        <div className={styles.emptyState}>
          No recipe execution data in the last {data?.hours ?? 168}h.
          Execute recipes via the order panel to build intelligence.
        </div>
      )}
    </div>
  )
}
