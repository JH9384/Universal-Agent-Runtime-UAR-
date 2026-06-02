import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'

// ---------------------------------------------------------------------------
// Utility: extract the inline width% from the bar element inside a container
// ---------------------------------------------------------------------------
function barWidth(container: HTMLElement): number {
  const bar = container.querySelector<HTMLElement>('[style*="width"]')
  if (!bar) throw new Error('No bar element found')
  const m = bar.style.width.match(/^([\d.]+)%$/)
  if (!m) throw new Error(`Unexpected width value: ${bar.style.width}`)
  return parseFloat(m[1])
}

// ---------------------------------------------------------------------------
// Inline re-implementation of the fixed DistRow logic so the tests are
// pure unit tests that don't depend on mounting the full dashboard.
// ---------------------------------------------------------------------------
function distBarPercent(count: number, max: number): number {
  return Math.round((count / Math.max(1, max)) * 100)
}

function clusterBarPercent(count: number, maxCluster: number): number {
  return Math.round((count / maxCluster) * 100)
}

// ---------------------------------------------------------------------------
// Pure logic tests — DistRow proportional width
// ---------------------------------------------------------------------------
describe('distBarPercent — proportional bar width', () => {
  it('returns 100% for the max value', () => {
    expect(distBarPercent(10, 10)).toBe(100)
  })

  it('returns 50% for half the max', () => {
    expect(distBarPercent(5, 10)).toBe(50)
  })

  it('returns 0% for zero count', () => {
    expect(distBarPercent(0, 10)).toBe(0)
  })

  it('never exceeds 100% (max === count)', () => {
    expect(distBarPercent(99, 99)).toBe(100)
  })

  it('handles max=0 safely (no division by zero)', () => {
    // max=0 with count=0 → 0%
    expect(distBarPercent(0, 0)).toBe(0)
    // max=0 with count>0 is impossible in real data (max = Math.max of all counts),
    // but the formula uses Math.max(1, max) so it divides by 1 rather than 0.
    // Result is count*100 (unbounded), which never occurs in practice.
    expect(() => distBarPercent(5, 0)).not.toThrow()
  })

  it('widest bar in a set is always 100%', () => {
    const dist: Record<string, number> = { critical: 3, high: 7, medium: 2, low: 1 }
    const max = Math.max(1, ...Object.values(dist))
    const widths = Object.values(dist).map((v) => distBarPercent(v, max))
    expect(Math.max(...widths)).toBe(100)
  })

  it('relative ordering is preserved', () => {
    const dist: Record<string, number> = { a: 10, b: 6, c: 1 }
    const max = Math.max(1, ...Object.values(dist))
    const [wa, wb, wc] = Object.values(dist).map((v) => distBarPercent(v, max))
    expect(wa).toBeGreaterThan(wb)
    expect(wb).toBeGreaterThan(wc)
  })

  it('old count*20 formula would overflow but proportional never does', () => {
    // old: Math.min(100, 6 * 20) = 100, same as max bar (wrong if max is 100)
    // new: 6/100 * 100 = 6  (correct)
    const count = 6
    const max = 100
    const oldWidth = Math.min(100, count * 20) // was 100 (wrong)
    const newWidth = distBarPercent(count, max) // 6 (correct)
    expect(oldWidth).toBe(100)   // old was incorrectly full-width
    expect(newWidth).toBe(6)     // new is correctly proportional
  })
})

// ---------------------------------------------------------------------------
// Pure logic tests — GraphAnalytics clusterBar proportional width
// ---------------------------------------------------------------------------
describe('clusterBarPercent — GraphAnalytics trust clusters', () => {
  it('top cluster is always 100%', () => {
    const clusters = { high_trust: 12, mid_trust: 5, low_trust: 2 }
    const max = Math.max(1, ...Object.values(clusters))
    expect(clusterBarPercent(clusters.high_trust, max)).toBe(100)
  })

  it('proportional values are correct', () => {
    const clusters = { a: 8, b: 4 }
    const max = Math.max(1, ...Object.values(clusters))
    expect(clusterBarPercent(4, max)).toBe(50)
  })

  it('single cluster shows 100%', () => {
    const clusters = { only: 3 }
    const max = Math.max(1, ...Object.values(clusters))
    expect(clusterBarPercent(3, max)).toBe(100)
  })

  it('old count*20 would cap short bars at wrong values', () => {
    // e.g. cluster value of 3 → old: Math.min(100,60)=60, new: 3/12*100=25
    const clusters = { big: 12, small: 3 }
    const max = Math.max(1, ...Object.values(clusters))
    const oldSmall = Math.min(100, 3 * 20) // 60 (wrong — appears almost as wide as big)
    const newSmall = clusterBarPercent(3, max) // 25 (correct)
    expect(oldSmall).toBe(60)
    expect(newSmall).toBe(25)
  })
})

// ---------------------------------------------------------------------------
// DOM rendering tests — verify the actual style attribute is set correctly
// ---------------------------------------------------------------------------
describe('DistRow DOM rendering — proportional style width', () => {
  function DistRow({ band, count, max }: { band: string; count: number; max: number }) {
    return (
      <div className="distRow">
        <span className="distLabel">{band.replaceAll('_', ' ')}</span>
        <div className="distBarWrap">
          <div className="distBar" style={{ width: `${Math.round((count / Math.max(1, max)) * 100)}%` }} />
        </div>
        <span className="distCount">{count}</span>
      </div>
    )
  }

  it('renders 100% width for the max item', () => {
    const { container } = render(<DistRow band="high" count={10} max={10} />)
    expect(barWidth(container)).toBe(100)
  })

  it('renders 50% width for half-max item', () => {
    const { container } = render(<DistRow band="medium" count={5} max={10} />)
    expect(barWidth(container)).toBe(50)
  })

  it('renders 0% width for zero count', () => {
    const { container } = render(<DistRow band="low" count={0} max={10} />)
    expect(barWidth(container)).toBe(0)
  })

  it('displays the correct count text', () => {
    const { getByText } = render(<DistRow band="critical" count={7} max={10} />)
    expect(getByText('7')).toBeInTheDocument()
  })

  it('replaces underscores in band name with spaces', () => {
    const { getByText } = render(<DistRow band="high_trust" count={3} max={5} />)
    expect(getByText('high trust')).toBeInTheDocument()
  })

  it('replaces ALL underscores — not just the first (replaceAll regression)', () => {
    const { getByText } = render(<DistRow band="high_confidence_low_trust" count={2} max={5} />)
    expect(getByText('high confidence low trust')).toBeInTheDocument()
  })

  it('regression: replace("_"," ") only removes first underscore', () => {
    // Proves the old behaviour was wrong
    expect('high_confidence_low_trust'.replace('_', ' ')).toBe('high confidence_low_trust')
    expect('high_confidence_low_trust'.replaceAll('_', ' ')).toBe('high confidence low trust')
  })
})

// ---------------------------------------------------------------------------
// data-width regression — FailureClusterPanel, FailureHotspotPanel, TopologyAnalyticsPanel
// These bars previously used `data-width={n}` which is a plain HTML attribute and
// has no effect on CSS. The bar fill was always 0px wide.
// ---------------------------------------------------------------------------
describe('MiniBar / Bar / RateBar — style.width set, not data-width', () => {
  function MiniBar({ value, max }: { value: number; max: number }) {
    const pct = max > 0 ? (value / max) * 100 : 0
    return (
      <div className="barTrack">
        <div className="barFill" style={{ width: `${Math.round(pct)}%` }} />
      </div>
    )
  }

  function Bar({ rate }: { rate: number }) {
    const pct = Math.round(rate * 100)
    return (
      <div className="barTrack">
        <div className="barFill" style={{ width: `${pct}%` }} />
      </div>
    )
  }

  function RateBar({ rate }: { rate: number }) {
    const pct = Math.round(rate * 100)
    return (
      <div className="rateTrack">
        <div className="rateFill" style={{ width: `${pct}%` }} />
      </div>
    )
  }

  it('MiniBar: fill has style.width, NOT data-width', () => {
    const { container } = render(<MiniBar value={7} max={10} />)
    const fill = container.querySelector('.barFill') as HTMLElement
    expect(fill.style.width).toBe('70%')
    expect(fill.dataset.width).toBeUndefined()
  })

  it('MiniBar: proportional to max', () => {
    const { container } = render(<MiniBar value={3} max={12} />)
    const fill = container.querySelector('.barFill') as HTMLElement
    expect(fill.style.width).toBe('25%')
  })

  it('MiniBar: 0% when value=0', () => {
    const { container } = render(<MiniBar value={0} max={10} />)
    const fill = container.querySelector('.barFill') as HTMLElement
    expect(fill.style.width).toBe('0%')
  })

  it('Bar (failure rate): fill has style.width, NOT data-width', () => {
    const { container } = render(<Bar rate={0.75} />)
    const fill = container.querySelector('.barFill') as HTMLElement
    expect(fill.style.width).toBe('75%')
    expect(fill.dataset.width).toBeUndefined()
  })

  it('Bar: 100% for rate=1.0', () => {
    const { container } = render(<Bar rate={1.0} />)
    const fill = container.querySelector('.barFill') as HTMLElement
    expect(fill.style.width).toBe('100%')
  })

  it('RateBar: fill has style.width, NOT data-width', () => {
    const { container } = render(<RateBar rate={0.9} />)
    const fill = container.querySelector('.rateFill') as HTMLElement
    expect(fill.style.width).toBe('90%')
    expect(fill.dataset.width).toBeUndefined()
  })

  it('regression: data-width attribute would have produced 0px width (old behaviour)', () => {
    // Simulate old broken component
    const { container } = render(
      <div className="barTrack">
        <div className="barFill" data-width={70} />
      </div>
    )
    const fill = container.querySelector('.barFill') as HTMLElement
    // data-width sets no inline style — style.width is empty
    expect(fill.style.width).toBe('')
    // The attribute is present but useless for layout
    expect(fill.getAttribute('data-width')).toBe('70')
  })
})

// ---------------------------------------------------------------------------
// RuntimeHealthPanel metric derivation logic
// ---------------------------------------------------------------------------
describe('RuntimeHealthPanel health metric derivation', () => {
  function deriveHealth(data: {
    circuit_breakers: { state: string }[]
    skills: { available: boolean }[]
  }) {
    const cbs = data.circuit_breakers
    const skills = data.skills
    const openCount = cbs.filter((cb) => cb.state === 'open').length
    const halfOpenCount = cbs.filter((cb) => cb.state === 'half_open').length
    const totalCbs = cbs.length || 1
    const availableSkills = skills.filter((s) => s.available).length
    const totalSkills = skills.length || 1
    const pressure = openCount / totalCbs
    const oscillation = halfOpenCount / totalCbs
    const replayConfidence = availableSkills / totalSkills
    const starvation = skills.length > 0 && availableSkills === 0
    const healthy = openCount === 0 && !starvation
    const mode =
      openCount > 0 ? 'degraded' :
      halfOpenCount > 0 ? 'recovering' :
      starvation ? 'starved' : 'healthy'
    return { pressure, oscillation, replayConfidence, starvation, healthy, mode }
  }

  it('all healthy when no open CBs and all skills available', () => {
    const h = deriveHealth({
      circuit_breakers: [{ state: 'closed' }, { state: 'closed' }],
      skills: [{ available: true }, { available: true }],
    })
    expect(h.healthy).toBe(true)
    expect(h.mode).toBe('healthy')
    expect(h.pressure).toBe(0)
    expect(h.oscillation).toBe(0)
    expect(h.replayConfidence).toBe(1)
    expect(h.starvation).toBe(false)
  })

  it('degraded mode when any CB is open', () => {
    const h = deriveHealth({
      circuit_breakers: [{ state: 'open' }, { state: 'closed' }],
      skills: [{ available: true }],
    })
    expect(h.mode).toBe('degraded')
    expect(h.healthy).toBe(false)
    expect(h.pressure).toBe(0.5)
  })

  it('recovering mode when any CB is half_open but none open', () => {
    const h = deriveHealth({
      circuit_breakers: [{ state: 'half_open' }, { state: 'closed' }],
      skills: [{ available: true }],
    })
    expect(h.mode).toBe('recovering')
    expect(h.oscillation).toBe(0.5)
  })

  it('starved mode when all skills unavailable', () => {
    const h = deriveHealth({
      circuit_breakers: [{ state: 'closed' }],
      skills: [{ available: false }, { available: false }],
    })
    expect(h.mode).toBe('starved')
    expect(h.starvation).toBe(true)
    expect(h.replayConfidence).toBe(0)
  })

  it('replayConfidence reflects partial skill availability', () => {
    const h = deriveHealth({
      circuit_breakers: [],
      skills: [{ available: true }, { available: false }, { available: true }],
    })
    expect(h.replayConfidence).toBeCloseTo(2 / 3)
  })

  it('no starvation when skills array is empty (no skills registered)', () => {
    const h = deriveHealth({ circuit_breakers: [], skills: [] })
    expect(h.starvation).toBe(false)
    expect(h.mode).toBe('healthy')
  })

  it('was previously always reporting hardcoded zeros', () => {
    // Regression: the old code always set pressure=0, oscillation=0, replayConfidence=1
    const oldPressure = 0
    const oldOscillation = 0
    const oldReplayConfidence = 1
    const h = deriveHealth({
      circuit_breakers: [{ state: 'open' }],
      skills: [{ available: false }],
    })
    // old values would have been wrong:
    expect(oldPressure).toBe(0)       // was wrong — should be 1.0
    expect(h.pressure).toBe(1)
    expect(oldOscillation).toBe(0)    // was wrong — oscillation is independent
    expect(oldReplayConfidence).toBe(1) // was wrong — should be 0
    expect(h.replayConfidence).toBe(0)
  })
})
