import { useState } from 'react'
import { authHeaders } from '../utils/auth'
import styles from './OperationalSearch.module.css'

interface SearchResult {
  _result_type: string
  _score: number
  [key: string]: any
}

const TYPE_ICONS: Record<string, string> = {
  run: '▶',
  incident: '⚠',
  recommendation: '💡',
  snapshot: '📸',
  alert: '🔔',
  inbox: '📥',
}

const TYPE_COLORS: Record<string, string> = {
  run: '#3b82f6',
  incident: '#ef4444',
  recommendation: '#22c55e',
  snapshot: '#06b6d4',
  alert: '#f97316',
  inbox: '#a855f7',
}

export function OperationalSearch({
  onOpenReplay,
  onOpenIncident,
}: {
  onOpenReplay?: (runId: string) => void
  onOpenIncident?: () => void
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setSearched(true)
    try {
      const res = await fetch(`/api/uar/search?q=${encodeURIComponent(query)}`, {
        headers: authHeaders(),
      })
      const json = await res.json()
      setResults(json.results || [])
      setCount(json.count || 0)
    } catch (e) {
      setResults([])
      setCount(0)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  const handleClick = (r: SearchResult) => {
    if (r._result_type === 'run' && r.id) {
      onOpenReplay?.(r.id)
    } else if (r._result_type === 'incident') {
      onOpenIncident?.()
    }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Operational Search</h4>
      </div>
      <div className={styles.searchRow}>
        <input
          className={styles.searchInput}
          placeholder="Search runs, incidents, recommendations, alerts..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button className={styles.searchBtn} onClick={handleSearch}>
          Search
        </button>
      </div>

      {loading && <div className={styles.loading}>Searching…</div>}

      {searched && !loading && (
        <div className={styles.meta}>{count} result(s)</div>
      )}

      <div className={styles.resultList}>
        {results.map((r, i) => (
          <button
            key={i}
            className={styles.resultCard}
            onClick={() => handleClick(r)}
          >
            <span
              className={styles.typeBadge}
              style={{ background: TYPE_COLORS[r._result_type] || '#94a3b8' }}
            >
              {TYPE_ICONS[r._result_type] || '•'} {r._result_type}
            </span>
            <span className={styles.resultTitle}>
              {r.title || r.id || r.message || JSON.stringify(r).slice(0, 60)}
            </span>
            {r.status && (
              <span className={styles.resultStatus}>{r.status}</span>
            )}
          </button>
        ))}
      </div>

      {searched && !loading && results.length === 0 && (
        <div className={styles.emptyState}>No results found.</div>
      )}
    </div>
  )
}
