import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ArtifactBrowser } from './ArtifactBrowser'

const mockListRuns = vi.fn()
const mockUseApiFetch = vi.fn()
const mockDownloadMarkdown = vi.fn()

vi.mock('../../api/dashboard', () => ({
  dashboardApi: {
    listRuns: (...args: unknown[]) => mockListRuns(...args),
  },
}))

vi.mock('../../hooks/useApiFetch', () => ({
  useApiFetch: (...args: unknown[]) => mockUseApiFetch(...args),
}))

vi.mock('../../utils/downloadMarkdown', () => ({
  downloadMarkdown: (...args: unknown[]) => mockDownloadMarkdown(...args),
  evidencePackFilename: () => 'uar-evidence-pack-test.md',
}))

beforeEach(() => {
  mockListRuns.mockReset()
  mockUseApiFetch.mockReset()
  mockDownloadMarkdown.mockReset()
  mockUseApiFetch.mockReturnValue({
    data: null,
    loading: false,
    error: null,
    refetch: vi.fn(),
  })
  Object.assign(navigator, {
    clipboard: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
  })
})

describe('ArtifactBrowser evidence preview', () => {
  it('renders Evidence Pack v2 preview from run records', async () => {
    mockListRuns.mockResolvedValue([
      { run_id: 'run-failed-1', status: 'failed', skills: ['echo'] },
      { run_id: 'run-complete-1', status: 'completed', skills: ['echo'] },
    ])

    render(<ArtifactBrowser />)

    expect(await screen.findByText('Evidence Pack v2 Preview')).toBeInTheDocument()
    expect(screen.getByText('warning')).toBeInTheDocument()
    expect(screen.getByText('run-failed-1')).toBeInTheDocument()
    expect(screen.getByText(/Fleet status: \*\*warning\*\*/)).toBeInTheDocument()
    expect(screen.getByText(/run:run-failed-1/)).toBeInTheDocument()
  })

  it('renders recurrence context from Mission Control incident summary', async () => {
    mockUseApiFetch.mockReturnValue({
      data: {
        incident_summary: {
          status: 'active',
          recurring_patterns: 1,
          top_pattern: {
            scope: 'service',
            value: 'svc-artifact',
            recurrence_count: 2,
            affected_run_ids: ['run-rec-2', 'run-rec-1'],
            latest_run_id: 'run-rec-2',
            linked_incident_ids: ['inc-artifact'],
            linked_recommendation_ids: ['rec-artifact'],
            evidence_refs: ['run:run-rec-2', 'run:run-rec-1'],
          },
        },
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
    })
    mockListRuns.mockResolvedValue([
      { run_id: 'run-complete-1', status: 'completed', skills: ['echo'] },
    ])

    render(<ArtifactBrowser />)

    expect(await screen.findByText('Top recurrence')).toBeInTheDocument()
    expect(screen.getByText('service:svc-artifact')).toBeInTheDocument()
    expect(screen.getByText('run-rec-2')).toBeInTheDocument()
    expect(screen.getByText(/Recurring patterns: \*\*1\*\*/)).toBeInTheDocument()
    expect(screen.getByText(/Incident IDs: `inc-artifact`/)).toBeInTheDocument()
  })

  it('copies Evidence Pack markdown', async () => {
    const user = userEvent.setup()
    mockListRuns.mockResolvedValue([
      { run_id: 'run-failed-2', status: 'failed', skills: ['echo'] },
    ])

    render(<ArtifactBrowser />)

    const button = await screen.findByRole('button', { name: 'Copy Evidence Markdown' })
    await user.click(button)

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining('run:run-failed-2')
    )
  })

  it('downloads Evidence Pack markdown', async () => {
    const user = userEvent.setup()
    mockListRuns.mockResolvedValue([
      { run_id: 'run-download-1', status: 'failed', skills: ['echo'] },
    ])

    render(<ArtifactBrowser />)

    const button = await screen.findByRole('button', { name: 'Download Evidence Markdown' })
    await user.click(button)

    expect(mockDownloadMarkdown).toHaveBeenCalledWith(
      'uar-evidence-pack-test.md',
      expect.stringContaining('run:run-download-1')
    )
  })
})
