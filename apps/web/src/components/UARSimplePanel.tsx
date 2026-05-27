import { useState, useRef, useCallback, useEffect } from 'react'
import { authHeaders } from '../utils/auth'
import styles from './UARSimplePanel.module.css'

const MAX_EVENTS = 500
const RECENT_KEY = 'uar.simple.recent'
const RECENT_MAX = 10

interface RecentRun {
  id: string
  goal: string
  status: string
  timestamp: number
  result?: string
  error?: string
}

const COMMON_SKILLS = [
  'openai_chat',
  'section_sum',
  'doc_ingest',
  'dependency_map',
  'sum_review',
  'ollama_generate',
  'graphrag_query',
  'math_compute',
  'uor_addr_canonicalize',
  'uor_ecosystem_status',
  'hologram_query',
  'hologram_status',
  'moltbook_list',
  'moltbook_search',
]

export function UARSimplePanel() {
  const [goal, setGoal] = useState('')
  const [selectedSkills, setSelectedSkills] = useState<string[]>(['openai_chat'])
  const [isRunning, setIsRunning] = useState(false)
  const [currentSkill, setCurrentSkill] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>(() => {
    try {
      const stored = localStorage.getItem(RECENT_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })

  const abortControllerRef = useRef<AbortController | null>(null)
  const eventCountRef = useRef(0)
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-dismiss errors after 8 seconds
  useEffect(() => {
    if (!error) return
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current)
    errorTimerRef.current = setTimeout(() => setError(''), 8000)
    return () => {
      if (errorTimerRef.current) clearTimeout(errorTimerRef.current)
    }
  }, [error])

  useEffect(() => {
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(recentRuns.slice(0, RECENT_MAX)))
    } catch {
      // Silently ignore quota exceeded / private browsing errors
    }
  }, [recentRuns])

  const toggleSkill = useCallback((skill: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skill)
        ? prev.filter((s) => s !== skill)
        : [...prev, skill]
    )
  }, [])

  const run = useCallback(async () => {
    if (!goal.trim() || isRunning) return
    setIsRunning(true)
    setCurrentSkill('Starting')
    setResult('')
    setError('')
    eventCountRef.current = 0

    abortControllerRef.current = new AbortController()
    const runId = `run-${Date.now()}`

    const body = {
      goal: goal.trim(),
      skills: selectedSkills,
    }

    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
    let decoder: TextDecoder | undefined
    let buffer = ''
    const outputs: string[] = []
    let finalStatus = 'failed'

    try {
      const res = await fetch('/api/uar/stream', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
        signal: abortControllerRef.current.signal,
      })

      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${res.statusText}${text ? ` — ${text}` : ''}`)
      }

      reader = res.body?.getReader()
      decoder = new TextDecoder()
      if (!reader) throw new Error('No response body reader available')

      while (true) {
        if (eventCountRef.current >= MAX_EVENTS) break
        const { done, value } = await reader.read()
        if (done) break
        if (abortControllerRef.current?.signal.aborted) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data:')) continue
            try {
              const json = JSON.parse(line.replace('data: ', ''))
              if (eventCountRef.current >= MAX_EVENTS) break
              eventCountRef.current++

              if (json.type === 'skill_start' && json.skill) {
                setCurrentSkill(json.skill)
              }
              if (json.type === 'skill_complete' && json.skill) {
                setCurrentSkill(`Completed: ${json.skill}`)
                if (json.payload?.result !== undefined) {
                  outputs.push(String(json.payload.result))
                }
              }
              if (json.type === 'error' && json.error) {
                setError(json.error)
              }
              if (json.type === 'run_complete' || json.type === 'complete') {
                finalStatus = json.payload?.status || 'completed'
                if (json.payload?.outputs?.length) {
                  for (const out of json.payload.outputs) {
                    if (typeof out === 'object' && out !== null) {
                      const vals = Object.values(out)
                      if (vals.length) outputs.push(String(vals[0]))
                    } else {
                      outputs.push(String(out))
                    }
                  }
                }
              }
            } catch {
              // ignore parse errors
            }
          }
        }
      }

      const combinedResult = outputs.join('\n\n').trim()
      setResult(combinedResult || 'Done')

      setRecentRuns((prev) => [
        {
          id: runId,
          goal: goal.trim(),
          status: finalStatus,
          timestamp: Date.now(),
          result: combinedResult,
          error: undefined,
        },
        ...prev,
      ].slice(0, RECENT_MAX))
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Stopped by user')
      } else {
        const msg = err instanceof Error ? err.message : 'Unknown error'
        setError(msg)
        setRecentRuns((prev) => [
          {
            id: runId,
            goal: goal.trim(),
            status: 'failed',
            timestamp: Date.now(),
            result: undefined,
            error: msg,
          },
          ...prev,
        ].slice(0, RECENT_MAX))
      }
    } finally {
      setIsRunning(false)
      setCurrentSkill('')
      if (reader) try { reader.releaseLock() } catch {}
    }
  }, [goal, isRunning, selectedSkills])

  // Keyboard shortcut: Ctrl/Cmd+Enter to run
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isRunning) {
        const target = e.target as HTMLElement
        if (target.tagName !== 'TEXTAREA') {
          e.preventDefault()
          run()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isRunning, run])

  const stop = useCallback(() => {
    abortControllerRef.current?.abort()
  }, [])

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h1>UAR</h1>
        <p className={styles.subtitle}>Universal Agent Runtime</p>
      </header>

      <section className={styles.inputSection}>
        <label className={styles.label}>What do you want to do?</label>
        <input
          type="text"
          className={styles.goalInput}
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && run()}
          placeholder="Describe your task..."
          disabled={isRunning}
        />
      </section>

      <section className={styles.skillsSection}>
        <label className={styles.label}>Skills</label>
        <div className={styles.skillChips}>
          {COMMON_SKILLS.map((skill) => (
            <button
              key={skill}
              type="button"
              className={`${styles.chip} ${selectedSkills.includes(skill) ? styles.chipActive : ''}`}
              onClick={() => toggleSkill(skill)}
              disabled={isRunning}
            >
              {skill.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </section>

      <section className={styles.actionSection}>
        <button
          type="button"
          className={`${styles.runBtn} ${isRunning ? styles.runBtnRunning : ''}`}
          onClick={isRunning ? stop : run}
          disabled={!goal.trim() && !isRunning}
          title={isRunning ? 'Stop execution' : 'Run (Ctrl+Enter)'}
        >
          {isRunning ? 'Stop' : 'Run'}
        </button>
        {currentSkill && (
          <span className={styles.status}>{currentSkill}</span>
        )}
      </section>

      {error && (
        <section className={styles.errorSection}>
          <p className={styles.errorText}>{error}</p>
        </section>
      )}

      {result && (
        <section className={styles.resultSection}>
          <label className={styles.label}>Result</label>
          <pre className={styles.resultBox}>{result}</pre>
        </section>
      )}

      {recentRuns.length > 0 && (
        <section className={styles.historySection}>
          <label className={styles.label}>Recent Runs</label>
          <ul className={styles.historyList}>
            {recentRuns.map((run) => (
              <li key={run.id} className={styles.historyItem}>
                <span className={styles.historyGoal}>{run.goal}</span>
                <span className={`${styles.historyStatus} ${run.status === 'completed' ? styles.statusOk : styles.statusFail}`}>
                  {run.status}
                </span>
                <span className={styles.historyTime}>
                  {new Date(run.timestamp).toLocaleTimeString()}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
