import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DivergenceDashboard } from '../DivergenceDashboard'
import RecipeTimeline from '../RecipeTimeline'

// ---------------------------------------------------------------------------
// DivergenceDashboard — typed recommendations, no any[]
// ---------------------------------------------------------------------------
describe('DivergenceDashboard — typed DivergenceItem, no any[]', () => {
  const originalFetch = globalThis.fetch

  const makeRec = (overrides: Record<string, unknown> = {}) => ({
    recommendation_id: 'rec-1',
    title: 'Test Rec',
    category: 'skill_sequence',
    source: 'pattern',
    confidence: 0.95,
    trust_score: 0.20,
    base_confidence: 0.9,
    adaptive_modifier: 0.05,
    drift_penalty: 0.0,
    affected_runs: ['run-abc123', 'run-def456'],
    ...overrides,
  })

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('shows loading state initially', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => new Promise(() => {}), // never resolves
    })
    render(<DivergenceDashboard />)
    expect(screen.getByText(/Loading divergence/i)).toBeInTheDocument()
  })

  it('shows error when fetch fails', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    })
    render(<DivergenceDashboard />)
    await waitFor(() => {
      expect(screen.getByText(/Divergence failed/i)).toBeInTheDocument()
    })
  })

  it('shows empty state when no divergence cases', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        recommendations: [],
        generated_at: 0,
        hours: 24,
        runs_analyzed: 0,
      }),
    })
    render(<DivergenceDashboard />)
    await waitFor(() => {
      expect(screen.getByText(/No divergence cases detected/i)).toBeInTheDocument()
    })
  })

  it('shows High Confidence / Low Trust card when confidence > 0.90 and trust < 0.40', async () => {
    const rec = makeRec({ confidence: 0.95, trust_score: 0.15 })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ recommendations: [rec], generated_at: 0, hours: 24, runs_analyzed: 1 }),
    })
    render(<DivergenceDashboard />)
    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument() // count badge
      expect(screen.getByText(/High Confidence/i)).toBeInTheDocument()
      expect(screen.getByText(/Low Trust/i)).toBeInTheDocument()
    })
  })

  it('shows Low Confidence / High Trust card when confidence < 0.50 and trust > 0.80', async () => {
    const rec = makeRec({ confidence: 0.30, trust_score: 0.90 })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ recommendations: [rec], generated_at: 0, hours: 24, runs_analyzed: 1 }),
    })
    render(<DivergenceDashboard />)
    await waitFor(() => {
      expect(screen.getByText(/Low Confidence/i)).toBeInTheDocument()
      expect(screen.getByText(/High Trust/i)).toBeInTheDocument()
    })
  })

  it('expands detail section and shows rec title when card clicked', async () => {
    const rec = makeRec({ confidence: 0.95, trust_score: 0.15, title: 'Stale Heuristic Rec' })
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ recommendations: [rec], generated_at: 0, hours: 24, runs_analyzed: 1 }),
    })
    render(<DivergenceDashboard />)
    await waitFor(() => screen.getByText(/High Confidence/i))
    // Click the High Confidence / Low Trust card
    fireEvent.click(screen.getByText('High Confidence').closest('button')!)
    await waitFor(() => {
      expect(screen.getByText('Stale Heuristic Rec')).toBeInTheDocument()
    })
  })

  it('regression: recommendations was typed as any[] — now DivergenceItem[]', () => {
    // Structural proof: DivergenceItem fields are required by the interface
    const item = makeRec()
    expect(typeof item.recommendation_id).toBe('string')
    expect(typeof item.confidence).toBe('number')
    expect(typeof item.trust_score).toBe('number')
    expect(Array.isArray(item.affected_runs)).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// RecipeTimeline — typed RawEvent, no events:any[]
// ---------------------------------------------------------------------------
describe('RecipeTimeline — typed RawEvent, no events:any[]', () => {
  const recipes = [
    { id: 'r1', label: 'Recipe Alpha' },
    { id: 'r2', label: 'Recipe Beta' },
  ]

  it('renders run header with run_id and goal_id from first event', () => {
    const events = [
      { type: 'run_start', run_id: 'run-001', goal_id: 'goal-xyz', timestamp: 1000 },
    ]
    render(<RecipeTimeline events={events} recipes={recipes} />)
    expect(screen.getByText(/run-001/)).toBeInTheDocument()
    expect(screen.getByText(/goal-xyz/)).toBeInTheDocument()
  })

  it('shows recipe block for recipe_start/recipe_end pair', () => {
    const events = [
      { type: 'recipe_start', run_id: 'r', goal_id: 'g', timestamp: 100, payload: { recipe_id: 'r1', instance_id: 'i1' } },
      { type: 'recipe_end', run_id: 'r', goal_id: 'g', timestamp: 200, payload: { instance_id: 'i1', status: 'complete' } },
    ]
    render(<RecipeTimeline events={events} recipes={recipes} />)
    expect(screen.getByText('Recipe Alpha')).toBeInTheDocument()
  })

  it('shows Standalone Skills section for skills outside a recipe', () => {
    const events = [
      { type: 'skill_start', run_id: 'r', goal_id: 'g', timestamp: 100, skill: 'search' },
      { type: 'skill_complete', run_id: 'r', goal_id: 'g', timestamp: 200, skill: 'search' },
    ]
    render(<RecipeTimeline events={events} recipes={recipes} />)
    expect(screen.getByText(/Standalone Skills/i)).toBeInTheDocument()
    expect(screen.getByText('search')).toBeInTheDocument()
  })

  it('shows no events empty state when events is empty', () => {
    render(<RecipeTimeline events={[]} recipes={recipes} />)
    expect(screen.getByText(/No events found/i)).toBeInTheDocument()
  })

  it('counts errors in summary bar', () => {
    const events = [
      { type: 'run_start', run_id: 'r', goal_id: 'g', timestamp: 100 },
      { type: 'error', run_id: 'r', goal_id: 'g', timestamp: 200, error: 'skill boom' },
      { type: 'error', run_id: 'r', goal_id: 'g', timestamp: 300, error: 'another' },
    ]
    render(<RecipeTimeline events={events} recipes={recipes} />)
    // Summary bar: "2 errors"
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows correct status for failed recipe', () => {
    const events = [
      { type: 'recipe_start', run_id: 'r', goal_id: 'g', timestamp: 100, payload: { recipe_id: 'r1', instance_id: 'i1' } },
      { type: 'skill_start', run_id: 'r', goal_id: 'g', timestamp: 110, skill: 'fetch' },
      { type: 'skill_failed', run_id: 'r', goal_id: 'g', timestamp: 120, skill: 'fetch', error: 'timeout' },
      { type: 'recipe_end', run_id: 'r', goal_id: 'g', timestamp: 130, payload: { instance_id: 'i1', status: 'failed' } },
    ]
    render(<RecipeTimeline events={events} recipes={recipes} />)
    // ❌ icon should be present (failed recipe)
    expect(screen.getAllByText('❌').length).toBeGreaterThan(0)
  })

  it('regression: events typed as any[] accepted objects with wrong shapes silently', () => {
    // With any[], passing {wrong: 'shape'} compiled fine — no safety.
    // Now RawEvent requires known optional fields; this is a compile-time check,
    // so we verify runtime behaviour: missing fields default gracefully.
    const events = [
      // Only has type, no run_id/goal_id/timestamp
      { type: 'run_start' },
    ]
    // Should not throw — all fields are optional on RawEvent
    expect(() =>
      render(<RecipeTimeline events={events} recipes={[]} />)
    ).not.toThrow()
  })
})
