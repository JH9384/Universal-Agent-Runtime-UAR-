/**
 * RE-AUDIT SPRINT Ω-2 — C4: Mission Control Certification
 *
 * Validates operator telemetry instrumentation:
 * - Evidence path completion rates
 * - Median investigation time
 * - Per-panel utility ranking
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  logAuditEvent,
  getAuditSummary,
  clearAuditEvents,
} from './analyticsInstrumentation'

describe('C4 Mission Control Certification', () => {
  beforeEach(() => {
    clearAuditEvents()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ----------------------------------------------------------------
  // MC-1: Evidence Path Completion
  // ----------------------------------------------------------------

  describe('MC-1 Evidence Path Completion', () => {
    it('completion rate 100% when all clicks load', () => {
      logAuditEvent('failure_cluster', 'r1', 'replay_clicked')
      logAuditEvent('replay_explorer', 'r1', 'replay_loaded')

      const s = getAuditSummary()
      expect(s.totalClicks).toBe(1)
      expect(s.totalLoaded).toBe(1)
      expect(s.completionRate).toBe(1)
    })

    it('completion rate 0% when no clicks load', () => {
      logAuditEvent('failure_cluster', 'r1', 'replay_clicked')

      const s = getAuditSummary()
      expect(s.completionRate).toBe(0)
    })

    it('completion rate 50% for mixed success', () => {
      logAuditEvent('failure_cluster', 'r1', 'replay_clicked')
      logAuditEvent('replay_explorer', 'r1', 'replay_loaded')
      logAuditEvent('failure_hotspot', 'r2', 'replay_clicked')

      const s = getAuditSummary()
      expect(s.totalClicks).toBe(2)
      expect(s.totalLoaded).toBe(1)
      expect(s.completionRate).toBe(0.5)
    })

    it('tracks replay_completed events separately', () => {
      logAuditEvent('failure_cluster', 'r1', 'replay_clicked')
      logAuditEvent('replay_explorer', 'r1', 'replay_loaded')
      logAuditEvent('replay_explorer', 'r1', 'replay_completed')

      const s = getAuditSummary()
      expect(s.totalCompleted).toBe(1)
    })

    it('load rate exceeds 95% threshold (certification)', () => {
      for (let i = 0; i < 97; i++) {
        logAuditEvent('failure_cluster', `r${i}`, 'replay_clicked')
        logAuditEvent('replay_explorer', `r${i}`, 'replay_loaded')
      }
      for (let i = 97; i < 100; i++) {
        logAuditEvent('failure_cluster', `r${i}`, 'replay_clicked')
      }

      const s = getAuditSummary()
      expect(s.completionRate).toBeGreaterThanOrEqual(0.95)
    })

    it('failure rate stays below 1% (certification)', () => {
      for (let i = 0; i < 199; i++) {
        logAuditEvent('failure_cluster', `r${i}`, 'replay_clicked')
        logAuditEvent('replay_explorer', `r${i}`, 'replay_loaded')
      }
      logAuditEvent('failure_cluster', 'r199', 'replay_clicked')

      const s = getAuditSummary()
      const failureRate = 1 - s.completionRate
      expect(failureRate).toBeLessThan(0.01)
    })
  })

  // ----------------------------------------------------------------
  // MC-2: Median Investigation Time
  // ----------------------------------------------------------------

  describe('MC-2 Median Investigation Time', () => {
    it('computes median click-to-load latency', () => {
      logAuditEvent('failure_cluster', 'r1', 'replay_clicked')
      vi.advanceTimersByTime(150)
      logAuditEvent('replay_explorer', 'r1', 'replay_loaded')

      const s = getAuditSummary()
      expect(s.medianTimeMs).toBe(150)
    })

    it('median under 2sec certification target', () => {
      for (let i = 0; i < 10; i++) {
        logAuditEvent('failure_cluster', `r${i}`, 'replay_clicked')
        vi.advanceTimersByTime(100 + i * 10)
        logAuditEvent('replay_explorer', `r${i}`, 'replay_loaded')
      }

      const s = getAuditSummary()
      expect(s.medianTimeMs).toBeLessThan(2000)
    })

    it('returns null when no paired click-load events', () => {
      logAuditEvent('failure_cluster', 'r1', 'replay_clicked')

      const s = getAuditSummary()
      expect(s.medianTimeMs).toBeNull()
    })

    it('ignores load without preceding click', () => {
      logAuditEvent('replay_explorer', 'r1', 'replay_loaded')
      logAuditEvent('failure_cluster', 'r2', 'replay_clicked')
      vi.advanceTimersByTime(200)
      logAuditEvent('replay_explorer', 'r2', 'replay_loaded')

      const s = getAuditSummary()
      expect(s.medianTimeMs).toBe(200)
    })
  })

  // ----------------------------------------------------------------
  // MC-4: Panel Utility Ranking
  // ----------------------------------------------------------------

  describe('MC-4 Panel Utility Ranking', () => {
    it('ranks panels by investigation count', () => {
      for (let i = 0; i < 3; i++) {
        logAuditEvent('failure_cluster', `r${i}`, 'replay_clicked')
        logAuditEvent('replay_explorer', `r${i}`, 'replay_loaded')
      }
      logAuditEvent('failure_hotspot', 'r3', 'replay_clicked')
      logAuditEvent('replay_explorer', 'r3', 'replay_loaded')

      const s = getAuditSummary()
      expect(s.byPanel.failure_cluster.clicks).toBe(3)
      expect(s.byPanel.failure_hotspot.clicks).toBe(1)
      expect(s.byPanel.recipe_intelligence).toBeUndefined()
    })

    it('computes per-panel completion rate', () => {
      logAuditEvent('failure_cluster', 'r1', 'replay_clicked')
      logAuditEvent('replay_explorer', 'r1', 'replay_loaded')
      logAuditEvent('failure_cluster', 'r2', 'replay_clicked')

      logAuditEvent('failure_hotspot', 'r3', 'replay_clicked')
      logAuditEvent('replay_explorer', 'r3', 'replay_loaded')

      const s = getAuditSummary()
      expect(s.byPanel.failure_cluster.rate).toBe(0.5)
      expect(s.byPanel.failure_hotspot.rate).toBe(1)
    })

    it('identifies dominant panel (Pareto check)', () => {
      for (let i = 0; i < 80; i++) {
        logAuditEvent('failure_cluster', `r${i}`, 'replay_clicked')
        logAuditEvent('replay_explorer', `r${i}`, 'replay_loaded')
      }
      for (let i = 80; i < 100; i++) {
        logAuditEvent('failure_hotspot', `r${i}`, 'replay_clicked')
        logAuditEvent('replay_explorer', `r${i}`, 'replay_loaded')
      }

      const s = getAuditSummary()
      const total = s.totalClicks
      const dominant = s.byPanel.failure_cluster.clicks / total
      expect(dominant).toBe(0.8)
    })
  })

  // ----------------------------------------------------------------
  // Edge Cases & Buffer Management
  // ----------------------------------------------------------------

  describe('Edge Cases', () => {
    it('handles empty event buffer', () => {
      const s = getAuditSummary()
      expect(s.totalClicks).toBe(0)
      expect(s.totalLoaded).toBe(0)
      expect(s.completionRate).toBe(0)
      expect(s.medianTimeMs).toBeNull()
      expect(Object.keys(s.byPanel)).toHaveLength(0)
    })

    it('pairs first click with first load for same run_id', () => {
      logAuditEvent('failure_cluster', 'r1', 'replay_clicked')
      vi.advanceTimersByTime(100)
      logAuditEvent('replay_explorer', 'r1', 'replay_loaded')
      vi.advanceTimersByTime(100)
      logAuditEvent('replay_explorer', 'r1', 'replay_loaded')

      const s = getAuditSummary()
      expect(s.medianTimeMs).toBe(100)
      expect(s.totalClicks).toBe(1)
      expect(s.totalLoaded).toBe(2)
    })
  })
})
