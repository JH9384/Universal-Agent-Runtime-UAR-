import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UARSimplePanel } from '../UARSimplePanel'

// @ts-ignore - global is provided by Vitest
declare const global: any

global.fetch = vi.fn()

describe('UARSimplePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(global.fetch).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        body: {
          getReader() {
            return {
              read() {
                return Promise.resolve({ done: true, value: undefined })
              },
              releaseLock() {},
            }
          },
        },
      } as Response)
    )
  })

  it('renders goal input and run button', () => {
    render(<UARSimplePanel />)
    expect(screen.getByPlaceholderText('Describe your task...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run/i })).toBeInTheDocument()
  })

  it('renders skill chips', () => {
    render(<UARSimplePanel />)
    expect(screen.getByText('openai chat')).toBeInTheDocument()
    expect(screen.getByText('section sum')).toBeInTheDocument()
  })

  it('toggles skill selection on click', () => {
    render(<UARSimplePanel />)
    const chip = screen.getByText('section sum')
    expect(chip.className).not.toMatch(/chipActive/)
    fireEvent.click(chip)
    expect(chip.className).toMatch(/chipActive/)
    fireEvent.click(chip)
    expect(chip.className).not.toMatch(/chipActive/)
  })

  it('disables run button when goal is empty', () => {
    render(<UARSimplePanel />)
    const btn = screen.getByRole('button', { name: /run/i })
    expect(btn).toBeDisabled()
  })

  it('enables run button when goal is entered', () => {
    render(<UARSimplePanel />)
    const input = screen.getByPlaceholderText('Describe your task...')
    fireEvent.change(input, { target: { value: 'test goal' } })
    const btn = screen.getByRole('button', { name: /run/i })
    expect(btn).not.toBeDisabled()
  })
})
