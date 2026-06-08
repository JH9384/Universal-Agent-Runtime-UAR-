import { describe, expect, it, vi } from 'vitest'
import { downloadMarkdown, evidencePackFilename } from './downloadMarkdown'


describe('downloadMarkdown', () => {
  it('creates and clicks a markdown download link', () => {
    const revokeObjectURL = vi.fn()
    const createObjectURL = vi.fn().mockReturnValue('blob:test-url')
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const click = vi.fn()
    const anchor = {
      href: '',
      download: '',
      click,
    } as unknown as HTMLAnchorElement
    const createElement = vi.spyOn(document, 'createElement').mockReturnValue(anchor)
    const appendChild = vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node)
    const removeChild = vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node)

    downloadMarkdown('pack.md', '# Pack')

    expect(createElement).toHaveBeenCalledWith('a')
    expect(anchor.href).toBe('blob:test-url')
    expect(anchor.download).toBe('pack.md')
    expect(click).toHaveBeenCalled()
    expect(appendChild).toHaveBeenCalledWith(anchor)
    expect(removeChild).toHaveBeenCalledWith(anchor)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:test-url')
  })
})

describe('evidencePackFilename', () => {
  it('builds a stable markdown filename from timestamp', () => {
    expect(evidencePackFilename(Date.UTC(2026, 5, 7, 12, 30, 0))).toBe(
      'uar-evidence-pack-2026-06-07T12-30-00-000Z.md'
    )
  })
})
