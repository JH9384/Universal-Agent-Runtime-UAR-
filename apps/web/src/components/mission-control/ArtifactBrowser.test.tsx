import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ArtifactBrowser } from './ArtifactBrowser'

const mockListRuns = vi.fn()

vi.mock('../../api/dashboard', () => ({
  dashboardApi: {
    listRuns: (...args: unknown[]) => mockListRuns(...args),
  },
}))

beforeEach(() => {
  mockListRuns.mockReset()
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
})
