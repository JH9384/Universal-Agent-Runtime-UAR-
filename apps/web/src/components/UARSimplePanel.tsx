import { useState, useRef, useCallback, useEffect } from 'react'
import { authHeaders } from '../utils/auth'
import { useDarkMode } from '../hooks/useDarkMode'
import { SkillGuide } from './SkillGuide'
import styles from './UARSimplePanel.module.css'

const MAX_EVENTS = 500
const RECENT_KEY = 'uar.simple.recent'
const RECENT_MAX = 10
const SKILLS_KEY = 'uar.simple.skills'

const DEFAULT_SKILLS = [
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

// Comprehensive registry of all known skills for the dropdown
const ALL_AVAILABLE_SKILLS = [
  // Core
  'doc_ingest', 'doc_ingest_enhanced', 'dependency_map', 'section_sum', 'sum_review', 'code_analysis',
  // AI / LLM
  'ollama_generate', 'openai_chat', 'openai_completion', 'openai_embedding',
  'lm_studio_chat', 'lm_studio_completion', 'lm_studio_embedding',
  'anthropic_chat', 'anthropic_completion', 'anthropic_embedding',
  'gemini_chat', 'gemini_completion', 'gemini_embedding',
  'mistral_chat', 'mistral_completion', 'mistral_embedding',
  'groq_chat', 'groq_completion', 'groq_embedding',
  'huggingface_chat', 'huggingface_completion', 'huggingface_embedding',
  'together_chat', 'together_completion', 'together_embedding',
  'optuna_tune', 'autogluon_ml', 'pycaret_ml', 'flaml_auto', 'chromadb_store',
  // Multi-Agent
  'agent_workflow', 'crewai_task', 'crewai_workflow',
  // Advanced RAG
  'llamaindex_rag', 'llamaindex_query',
  // Pipeline
  'dagster_pipeline', 'dagster_status',
  // Governance
  'guardrail_check', 'budget_status', 'blackboard_status', 'blackboard_message',
  // GraphRAG
  'graphrag_init', 'graphrag_index', 'graphrag_query', 'flexible_graphrag',
  // Autonomi
  'autonomi_upload', 'autonomi_download', 'autonomi_status',
  // ALM
  'alm_analyze', 'alm_generate', 'alm_verify',
  // UOR
  'uor_addr_canonicalize', 'uor_addr_resolve',
  'hologram_query', 'hologram_status',
  'moltbook_list', 'moltbook_search', 'moltbook_post',
  'prism_btc_anchor', 'prism_btc_verify',
  'severance_infer', 'severance_verify',
  'anunix_health', 'anunix_run',
  'uor_ecosystem_status',
  // STEM
  'math_compute', 'math_plot', 'math_plot_3d',
  'cipher_ops', 'physics_compute', 'diff_eq_solve',
  'cern_root', 'scipy_opt',
  'quantum_circuit', 'quantum_ml',
  'chem_analysis', 'bio_compute', 'relativity',
  'data_viz_3d', 'trefoil_simulation', 'molecular_visualization', 'quantum_circuit_visualization',
  // Hardware
  'fpga_verify', 'verilog_parse', 'myhdl_design',
  'riscv_sim', 'riscv_cycle', 'verilator_sim',
  'micropython', 'platformio',
  // CV
  'yolo_detect', 'opencv_process', 'video_analyze', 'face_recognize',
  // Blockchain
  'solana_tx', 'smart_contract', 'nft_mint',
  // MLOps
  'mlflow_track', 'mlflow_deploy', 'kubeflow_pipe', 'model_reg',
  // Security
  'pentest_scan', 'osint_recon', 'crypto_analyze', 'security_audit',
  // Data Engineering
  'airflow_dag', 'dbt_transform', 'snowflake_etl', 'spark_process',
]

interface RecipeDef {
  id: string
  label: string
  skills: string[]
}

const DEFAULT_RECIPES: RecipeDef[] = [
  { id: 'review', label: '🦙 Ollama review', skills: ['doc_ingest', 'ollama_generate'] },
  { id: 'deps', label: '🕸️ Dep map', skills: ['doc_ingest', 'dependency_map', 'sum_review'] },
  { id: 'gr_index', label: '📚 GraphRAG index', skills: ['graphrag_index'] },
  { id: 'gr_query', label: '🔍 GraphRAG query', skills: ['graphrag_query'] },
]

interface RecentRun {
  id: string
  goal: string
  status: string
  timestamp: number
  result?: string
  error?: string
}

interface UARSimplePanelProps {
  onToggleMode?: () => void
  modeLabel?: string
}

export function UARSimplePanel({ onToggleMode, modeLabel }: UARSimplePanelProps) {
  const [goal, setGoal] = useState('')
  const [selectedSkills, setSelectedSkills] = useState<string[]>(['openai_chat'])
  const [selectedRecipes, setSelectedRecipes] = useState<string[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [currentSkill, setCurrentSkill] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [darkMode, setDarkMode] = useDarkMode()
  const [showHelp, setShowHelp] = useState(false)
  const [skillGuideOpen, setSkillGuideOpen] = useState(false)
  const [uorImageError, setUorImageError] = useState(false)
  const [editableSkills, setEditableSkills] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(SKILLS_KEY)
      return stored ? JSON.parse(stored) : DEFAULT_SKILLS
    } catch {
      return DEFAULT_SKILLS
    }
  })
  const [isEditingSkills, setIsEditingSkills] = useState(false)
  const [newSkillInput, setNewSkillInput] = useState('')
  const [editingSkill, setEditingSkill] = useState<string | null>(null)
  const [editSkillValue, setEditSkillValue] = useState('')

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

  useEffect(() => {
    try {
      localStorage.setItem(SKILLS_KEY, JSON.stringify(editableSkills))
    } catch {
      // ignore
    }
  }, [editableSkills])

  const toggleSkill = useCallback((skill: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skill)
        ? prev.filter((s) => s !== skill)
        : [...prev, skill]
    )
  }, [])

  const toggleRecipe = useCallback((recipeId: string) => {
    setSelectedRecipes((prev) =>
      prev.includes(recipeId)
        ? prev.filter((r) => r !== recipeId)
        : [...prev, recipeId]
    )
  }, [])

  const [addMode, setAddMode] = useState<'skill' | 'recipe'>('skill')
  const [editableRecipes, setEditableRecipes] = useState<RecipeDef[]>([])

  const removeSkillFromList = useCallback((skill: string) => {
    setEditableSkills((prev) => prev.filter((s) => s !== skill))
    setSelectedSkills((prev) => prev.filter((s) => s !== skill))
  }, [])

  const startEditSkill = useCallback((skill: string) => {
    setEditingSkill(skill)
    setEditSkillValue(skill.replace(/_/g, ' '))
  }, [])

  const saveEditSkill = useCallback(() => {
    if (!editingSkill) return
    const raw = editSkillValue.trim().toLowerCase().replace(/\s+/g, '_')
    if (!raw || (raw !== editingSkill && editableSkills.includes(raw))) {
      setEditingSkill(null)
      return
    }
    setEditableSkills((prev) =>
      prev.map((s) => (s === editingSkill ? raw : s))
    )
    setSelectedSkills((prev) =>
      prev.map((s) => (s === editingSkill ? raw : s))
    )
    setEditingSkill(null)
    setEditSkillValue('')
  }, [editingSkill, editSkillValue, editableSkills])

  const run = useCallback(async () => {
    if (!goal.trim() || isRunning) return
    setIsRunning(true)
    setCurrentSkill('Starting')
    setResult('')
    setError('')
    eventCountRef.current = 0

    abortControllerRef.current = new AbortController()
    const runId = `run-${Date.now()}`

    const executionOrder = [
      ...selectedSkills.map((s, i) => ({ type: 'skill' as const, content: s, id: `skill-${s}-${i}` })),
      ...selectedRecipes.map((r, i) => ({ type: 'recipe' as const, content: r, id: `recipe-${r}-${i}` })),
    ]
    const body: Record<string, unknown> = {
      goal: goal.trim(),
      skills: selectedSkills,
    }
    if (selectedRecipes.length > 0) {
      body.execution_order = executionOrder
      const recipeDefs = editableRecipes
        .filter((r) => selectedRecipes.includes(r.id))
        .map((r) => ({ id: r.id, label: r.label, skills: r.skills }))
      if (recipeDefs.length) {
        body.metadata = { recipe_definitions: recipeDefs }
      }
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
  }, [goal, isRunning, selectedSkills, selectedRecipes, editableRecipes])

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
      <div className={styles.headerBar}>
        <h3 className={styles.headerTitle}>🤖 Universal Agent Runtime (UAR)</h3>
        <button
          onClick={() => setDarkMode(!darkMode)}
          className={styles.skillGuideButton}
          title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {darkMode ? '☀️' : '🌙'}
        </button>
        <button
          onClick={() => setShowHelp(!showHelp)}
          className={styles.skillGuideButton}
          title="Toggle quick start tips"
          aria-label="Toggle quick start tips"
        >
          💡
        </button>
        <button
          onClick={() => setSkillGuideOpen(true)}
          className={styles.skillGuideButton}
          title="View detailed skill documentation"
          aria-label="View detailed skill documentation"
        >
          📘
        </button>
        {onToggleMode && (
          <button
            onClick={onToggleMode}
            className={styles.skillGuideButton}
            title={`Switch to ${modeLabel} mode`}
            aria-label={`Switch to ${modeLabel} mode`}
          >
            {modeLabel}
          </button>
        )}
        <span className={styles.projectRoot}>UOR Support <a href="https://uor.foundation" target="_blank" rel="noopener noreferrer">{uorImageError ? <span className={styles.uorFallbackIcon}>🔗</span> : <img src="https://uor.foundation/assets/uor-icon-new-CQuNVmtH.png" alt="UOR" width="20" height="20" className={styles.uorIcon} onError={() => setUorImageError(true)} />}</a></span>
      </div>

      {showHelp && (
        <div className={styles.helpBox}>
          <div className={styles.helpSection}>
            <strong>Quick Start:</strong>
            <ul className={styles.helpList}>
              <li>1. <strong>Type your goal</strong> in the input below</li>
              <li>2. <strong>Select skills</strong> by clicking the chips</li>
              <li>3. <strong>Click Run</strong> or press Ctrl+Enter to execute</li>
              <li>4. <strong>Watch</strong> real-time progress and results</li>
            </ul>
          </div>
        </div>
      )}

      {skillGuideOpen && (
        <div className={styles.skillGuideModalOverlay} onClick={() => setSkillGuideOpen(false)}>
          <div className={styles.skillGuideModalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.skillGuideModalHeader}>
              <strong>Skill Guide</strong>
              <button className={styles.modalCloseButton} onClick={() => setSkillGuideOpen(false)} aria-label="Close skill guide">✕</button>
            </div>
            <div className={styles.skillGuideModalBody}>
              <SkillGuide />
            </div>
          </div>
        </div>
      )}

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
        <div className={styles.skillsSectionHeader}>
          <label className={styles.label}>Skills</label>
          <button
            type="button"
            className={`${styles.editSkillsButton} ${isEditingSkills ? styles.editSkillsButtonActive : ''}`}
            onClick={() => {
              setIsEditingSkills((v) => !v)
              setEditingSkill(null)
            }}
            disabled={isRunning}
            title={isEditingSkills ? 'Done editing' : 'Edit skills'}
          >
            {isEditingSkills ? 'Done' : 'Edit'}
          </button>
        </div>
        <div className={styles.skillChips}>
          {editableSkills.map((skill) => (
            <div key={skill} className={styles.chipWrapper}>
              {editingSkill === skill ? (
                <input
                  type="text"
                  className={styles.chipEditInput}
                  value={editSkillValue}
                  onChange={(e) => setEditSkillValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveEditSkill()
                    if (e.key === 'Escape') {
                      setEditingSkill(null)
                      setEditSkillValue('')
                    }
                  }}
                  onBlur={saveEditSkill}
                  autoFocus
                  aria-label="Edit skill name"
                />
              ) : (
                <button
                  type="button"
                  className={`${styles.chip} ${selectedSkills.includes(skill) ? styles.chipActive : ''}`}
                  onClick={() => {
                    if (isEditingSkills) startEditSkill(skill)
                    else toggleSkill(skill)
                  }}
                  disabled={isRunning}
                  title={isEditingSkills ? 'Click to edit name' : 'Toggle skill'}
                >
                  {skill.replace(/_/g, ' ')}
                </button>
              )}
              {isEditingSkills && (
                <button
                  type="button"
                  className={styles.chipRemove}
                  onClick={() => removeSkillFromList(skill)}
                  disabled={isRunning}
                  aria-label={`Remove ${skill}`}
                  title="Remove skill"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          {editableRecipes.map((recipe) => (
            <div key={recipe.id} className={styles.chipWrapper}>
              <button
                type="button"
                className={`${styles.chip} ${styles.recipeChip} ${selectedRecipes.includes(recipe.id) ? styles.chipActive : ''}`}
                onClick={() => toggleRecipe(recipe.id)}
                disabled={isRunning}
                title={recipe.label}
              >
                {recipe.label}
              </button>
              {isEditingSkills && (
                <button
                  type="button"
                  className={styles.chipRemove}
                  onClick={() => {
                    setEditableRecipes((prev) => prev.filter((r) => r.id !== recipe.id))
                    setSelectedRecipes((prev) => prev.filter((r) => r !== recipe.id))
                  }}
                  disabled={isRunning}
                  aria-label={`Remove ${recipe.id}`}
                  title="Remove recipe"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
        {isEditingSkills && (
          <div className={styles.addSkillRow}>
            <select
              className={styles.addSkillSelect}
              value={newSkillInput}
              onChange={(e) => {
                const val = e.target.value
                if (!val) return
                setNewSkillInput(val)
                if (addMode === 'skill') {
                  if (!editableSkills.includes(val)) {
                    setEditableSkills((prev) => [...prev, val])
                  }
                } else {
                  if (!editableRecipes.some((r) => r.id === val)) {
                    const recipe = DEFAULT_RECIPES.find((r) => r.id === val)
                    if (recipe) setEditableRecipes((prev) => [...prev, recipe])
                  }
                }
                setNewSkillInput('')
              }}
              disabled={isRunning}
              aria-label={`Select ${addMode} to add`}
            >
              <option value="">{addMode === 'skill' ? '-- Select skill --' : '-- Select recipe --'}</option>
              {addMode === 'skill'
                ? ALL_AVAILABLE_SKILLS
                  .filter((s) => !editableSkills.includes(s))
                  .map((s) => (
                    <option key={s} value={s}>
                      {s.replace(/_/g, ' ')}
                    </option>
                  ))
                : DEFAULT_RECIPES
                  .filter((r) => !editableRecipes.some((er) => er.id === r.id))
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
            </select>
            <div className={styles.addModeToggle}>
              <button
                type="button"
                className={`${styles.addModeButton} ${addMode === 'skill' ? styles.addModeButtonActive : ''}`}
                onClick={() => setAddMode('skill')}
              >
                Skill
              </button>
              <button
                type="button"
                className={`${styles.addModeButton} ${addMode === 'recipe' ? styles.addModeButtonActive : ''}`}
                onClick={() => setAddMode('recipe')}
              >
                Recipe
              </button>
            </div>
          </div>
        )}
        {(selectedSkills.length > 0 || selectedRecipes.length > 0) && (
          <div className={styles.selectedSkillsBox}>
            <div className={styles.selectedSkillsHeader}>
              <span className={styles.selectedSkillsLabel}>Selected ({selectedSkills.length + selectedRecipes.length})</span>
              <button
                type="button"
                className={styles.clearSkillsButton}
                onClick={() => { setSelectedSkills([]); setSelectedRecipes([]) }}
                disabled={isRunning}
                title="Clear all selections"
              >
                Clear
              </button>
            </div>
            <div className={styles.selectedSkillsList}>
              {selectedSkills.map((skill, index) => (
                <div key={`skill-${skill}-${index}`} className={styles.selectedSkillItem}>
                  <span className={styles.selectedSkillIndex}>{index + 1}</span>
                  <span className={styles.selectedSkillName}>{skill.replace(/_/g, ' ')}</span>
                  <button
                    type="button"
                    className={styles.removeSkillButton}
                    onClick={() => toggleSkill(skill)}
                    disabled={isRunning}
                    aria-label={`Remove ${skill}`}
                    title="Remove"
                  >
                    ✕
                  </button>
                </div>
              ))}
              {selectedRecipes.map((recipeId, index) => {
                const recipe = editableRecipes.find((r) => r.id === recipeId) || DEFAULT_RECIPES.find((r) => r.id === recipeId)
                const displayIndex = selectedSkills.length + index + 1
                return (
                  <div key={`recipe-${recipeId}-${index}`} className={`${styles.selectedSkillItem} ${styles.selectedRecipeItem}`}>
                    <span className={styles.selectedSkillIndex}>{displayIndex}</span>
                    <span className={styles.selectedSkillName}>🍳 {recipe?.label || recipeId}</span>
                    <button
                      type="button"
                      className={styles.removeSkillButton}
                      onClick={() => toggleRecipe(recipeId)}
                      disabled={isRunning}
                      aria-label={`Remove ${recipeId}`}
                      title="Remove"
                    >
                      ✕
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )}
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
